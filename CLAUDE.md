# Specific guidelines and checks at all times

## General checks
- Python 3.12 type hinting without typing package reliance, if anything remove them never include them in any of the code.
- Avoid creating new python modules for duplicated functionalities.
- Are the markdown files for design docs fully updated with implementations? If not, update them at all times.
- Whenever you are logging or showing output, dont use [:..] to only take the first number of tokens, show the entire content.

## Functional checks
- Look into the livewell case study and the TODOS.md, see the gap with Agents.md. we need to implement and strengthen the agentic pattern here. Then run run_demo.py to make sure. Agents.md need to be up-to-date with every code change. Can you double check what you are going to do in details, run it through me first?
