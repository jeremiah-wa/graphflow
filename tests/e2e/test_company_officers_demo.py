"""End-to-end test for the company_officers demo connector.

This test exercises the full GraphFlow pipeline from manifest validation
through Neo4j loading, including idempotency verification.
"""

import os
from pathlib import Path

import pytest
from neo4j import GraphDatabase
from typer.testing import CliRunner

from graphflow_core.cli.main import app


@pytest.mark.e2e
class TestCompanyOfficersDemo:
    """E2E test for the company_officers example."""

    @pytest.fixture
    def example_path(self) -> Path:
        """Path to the company_officers example."""
        return Path("examples/company_officers")

    @pytest.fixture
    def neo4j_driver(self):
        """Neo4j driver for verification queries."""
        uri = os.environ.get("GRAPHFLOW_NEO4J_URI", "bolt://localhost:7687")
        username = os.environ.get("GRAPHFLOW_NEO4J_USERNAME", "neo4j")
        password = os.environ.get("GRAPHFLOW_NEO4J_PASSWORD", "")
        
        if not password:
            pytest.skip("GRAPHFLOW_NEO4J_PASSWORD not set")
            
        driver = GraphDatabase.driver(uri, auth=(username, password))
        yield driver
        driver.close()

    @pytest.fixture(autouse=True)
    def clean_neo4j(self, neo4j_driver):
        """Clean Neo4j before and after each test."""
        with neo4j_driver.session() as session:
            # Clean before test
            session.run("MATCH (n) DETACH DELETE n")
            
        yield
        
        with neo4j_driver.session() as session:
            # Clean after test
            session.run("MATCH (n) DETACH DELETE n")

    def test_validate_manifests(self, example_path: Path):
        """Test that the demo manifests are valid."""
        runner = CliRunner()
        result = runner.invoke(app, ["config", "validate", str(example_path)])
        
        assert result.exit_code == 0
        assert "OK:" in result.stdout
        assert "company_officers_csv" in result.stdout
        assert "company_network" in result.stdout
        assert "company_officers_pipeline" in result.stdout

    def test_ingest_preview(self, example_path: Path):
        """Test data ingestion preview."""
        runner = CliRunner()
        result = runner.invoke(app, ["ingest", str(example_path), "--limit", "3"])
        
        assert result.exit_code == 0
        assert "Source: company_officers_csv" in result.stdout
        assert "Records: 8" in result.stdout
        assert "TechCorp Limited" in result.stdout
        assert "Sarah Johnson" in result.stdout

    def test_mapping_preview(self, example_path: Path):
        """Test graph mapping preview."""
        runner = CliRunner()
        result = runner.invoke(app, ["map", str(example_path)])
        
        assert result.exit_code == 0
        assert "Records read: 8" in result.stdout
        assert "Nodes produced: 9" in result.stdout  # 4 companies + 5 people
        assert "Relationships produced: 8" in result.stdout
        assert "Issues: 0 error(s), 0 warning(s)" in result.stdout

    def test_neo4j_connectivity(self, example_path: Path):
        """Test Neo4j connectivity check."""
        runner = CliRunner()
        result = runner.invoke(app, ["graph", "ping", str(example_path)])
        
        assert result.exit_code == 0
        assert "Neo4j connection successful" in result.stdout

    def test_load_graph_first_run(self, example_path: Path, neo4j_driver):
        """Test loading the graph for the first time."""
        runner = CliRunner()
        result = runner.invoke(app, ["load", str(example_path)])
        
        assert result.exit_code == 0
        assert "Loading complete" in result.stdout
        
        # Verify the graph content
        with neo4j_driver.session() as session:
            # Count nodes
            company_count = session.run(
                "MATCH (c:Company) RETURN COUNT(c) AS count"
            ).single()["count"]
            person_count = session.run(
                "MATCH (p:Person) RETURN COUNT(p) AS count"
            ).single()["count"]
            rel_count = session.run(
                "MATCH ()-[r:OFFICER_OF]->() RETURN COUNT(r) AS count"
            ).single()["count"]
            
            assert company_count == 4
            assert person_count == 5
            assert rel_count == 8
            
            # Verify specific data
            sarah = session.run(
                "MATCH (p:Person {person_id: 'P001'}) RETURN p.name AS name"
            ).single()
            assert sarah["name"] == "Sarah Johnson"
            
            # Verify Sarah's directorships
            sarah_companies = session.run(
                """
                MATCH (p:Person {person_id: 'P001'})-[:OFFICER_OF]->(c:Company)
                RETURN c.name AS company
                ORDER BY company
                """
            ).values("company")
            assert sarah_companies == ["Global Innovations PLC", "TechCorp Limited"]

    def test_load_graph_idempotency(self, example_path: Path, neo4j_driver):
        """Test that re-loading is idempotent."""
        runner = CliRunner()
        
        # First load
        result1 = runner.invoke(app, ["load", str(example_path)])
        assert result1.exit_code == 0
        
        # Get initial counts
        with neo4j_driver.session() as session:
            initial_nodes = session.run(
                "MATCH (n) RETURN COUNT(n) AS count"
            ).single()["count"]
            initial_rels = session.run(
                "MATCH ()-[r]->() RETURN COUNT(r) AS count"
            ).single()["count"]
        
        # Second load - should not create duplicates
        result2 = runner.invoke(app, ["load", str(example_path)])
        assert result2.exit_code == 0
        
        # Verify counts unchanged
        with neo4j_driver.session() as session:
            final_nodes = session.run(
                "MATCH (n) RETURN COUNT(n) AS count"
            ).single()["count"]
            final_rels = session.run(
                "MATCH ()-[r]->() RETURN COUNT(r) AS count"
            ).single()["count"]
        
        assert final_nodes == initial_nodes
        assert final_rels == initial_rels

    def test_complex_queries(self, example_path: Path, neo4j_driver):
        """Test complex graph queries after loading."""
        runner = CliRunner()
        result = runner.invoke(app, ["load", str(example_path)])
        assert result.exit_code == 0
        
        with neo4j_driver.session() as session:
            # Find people with multiple directorships
            multi_directors = session.run(
                """
                MATCH (p:Person)-[r:OFFICER_OF {role: "director"}]->(c:Company)
                WITH p, COUNT(c) AS companies
                WHERE companies > 1
                RETURN p.name AS name, companies
                ORDER BY companies DESC, name
                """
            ).data()
            
            assert len(multi_directors) == 1
            assert multi_directors[0]["name"] == "Sarah Johnson"
            assert multi_directors[0]["companies"] == 2
            
            # Check dissolved company
            dissolved = session.run(
                """
                MATCH (c:Company {status: "dissolved"})
                RETURN c.name AS name, c.company_number AS number
                """
            ).single()
            
            assert dissolved["name"] == "CloudBase Holdings"
            assert dissolved["number"] == "99887766"
            
            # Verify officer movements
            emma_history = session.run(
                """
                MATCH (p:Person {name: "Emma Williams"})-[r:OFFICER_OF]->(c:Company)
                RETURN c.name AS company, r.appointed_date AS appointed
                ORDER BY r.appointed_date
                """
            ).data()
            
            assert len(emma_history) == 2
            assert emma_history[0]["company"] == "DataFlow Systems Ltd"
            assert emma_history[1]["company"] == "TechCorp Limited"
