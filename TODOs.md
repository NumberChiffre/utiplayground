# TODOs for Livewell Case Study

The purpose of the TODOs is to bridge the gap between the Livewell case study problem and the code implementations + markdown content (words and diagrams).

## UTI Assessment Algorithm
- What is the use case of this algorithm (deterministic) and the integration with agents (non-deterministic)?
- Do we rely fully on the uti assessment algorithm to deterministically generate recommendations and initial assessments, then let the agents check as doctor, pharmacists, and gather evidence for a better assessed treatment filtered for counterarguments and fact-checks?
- What is the point of doctor/pharmacist agents and how do they improve the uti assessment algorithm?
- Are we missing any context or inputs before reaching the uti assessment algorithm?

## Agents
- Current agentic pattern is parallelization and integrated structured output to a single agent via a single model. I think there needs to be some sort of a feedback loop between agents, for instance a UTI doctor agent (urology?) interacts with a hospital pharmacist agent, and pharmacist agent provides feedback to UTI doctor agent for any concerns, and then go to the next step.
- Clinical reasoning, citations, and just extracting claims. Then for each citation, show the rationale of its relevance to its existence. 
- After we produce the final agent, can we produce a final markdown report with all the analysis and decisions we provided? Can we use this to respond to any question the client may have?
- Can we use different models for different agents, like GPT-5 for reasoning parts for agents, web search could use GPT-4.1. 
- [Optional] Agentic memory, yes, for a patient, conditions may evolve over time, we need to remember and update.

## Evaluation and Improvement
- Write a detailed markdown document (heavily descriptive and mermaid diagrams) addressing:
    - How would you evaluate the LLM responses and clinical decisions over time?
    - Who (human reviewers, doctors, patients) would you involve in the evaluation loop and how?
    - How would you use these evaluations to improve the agent’s quality and safety?
    - How would you engineer and deploy this eval+improvement system?
- Key thing we are testing: your conceptual understanding of how to evaluate, improve, and deploy ML/LLM/agent systems at scale.