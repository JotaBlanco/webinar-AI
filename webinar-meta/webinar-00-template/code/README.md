# code

The project's own implementation — model, calculator, analyzer, simulator. The thing that already exists in your engineering team and that the agent works *with*, not *replaces*.

## What goes here

Domain code in whatever language your team uses — Python, MATLAB, C++, R, Verilog, Modelica. The template ships with an empty Python package (`__init__.py`) because the rest of the template is Python-flavoured, but there is no requirement to stay in Python.

## What does NOT go here

- **Tool wrappers** for the agent — those go in `tools/`. `tools/` *imports from* `code/`; never the other way around.
- **Evals / sensors** — those go in `evals/`. Evals may import from `code/` but `code/` should never import from `evals/`.
- **Data** — goes in `data/`.

## Rule of thumb for the boundary

If you'd ship it as part of your engineering team's normal product/research, it goes in `code/`. If it only exists to expose `code/` to an agent or to score an agent's output, it goes in `tools/` or `evals/`.

## Template state

Empty Python package. Add your domain code here.
