PYTHON ?= python3
test:
	$(PYTHON) -m unittest discover -s tests -v
run:
	$(PYTHON) agent.py --task "$(TASK)"
