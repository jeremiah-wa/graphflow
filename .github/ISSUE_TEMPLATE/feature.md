---
name: Feature
description: Request or plan a user-facing or platform capability
title: ""
labels: ["Feature"]
body:
  - type: markdown
    attributes:
      value: |
        Use this template for new GraphFlow capabilities or implementation slices.
  - type: textarea
    id: goal
    attributes:
      label: Goal
      description: What outcome should this issue achieve?
      placeholder: Describe the desired outcome.
    validations:
      required: true
  - type: textarea
    id: context
    attributes:
      label: Context
      description: Why does this matter and how does it fit the roadmap?
    validations:
      required: false
  - type: textarea
    id: scope
    attributes:
      label: Scope
      description: What is included?
      value: |
        - 
        - 
        - 
    validations:
      required: true
  - type: textarea
    id: out_of_scope
    attributes:
      label: Out of scope
      description: What is deliberately excluded or deferred?
      value: |
        - 
    validations:
      required: false
  - type: textarea
    id: acceptance_criteria
    attributes:
      label: Acceptance criteria
      description: What must be true for this issue to be done?
      value: |
        - [ ] 
        - [ ] 
        - [ ] Tests/docs updated where relevant
    validations:
      required: true
  - type: textarea
    id: notes
    attributes:
      label: Notes
      description: Implementation hints, links, or follow-up ideas.
    validations:
      required: false
---
