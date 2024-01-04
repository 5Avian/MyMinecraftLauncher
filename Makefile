run:
	python MyMinecraftLauncher.py

fmt:
	python -m isort MyMinecraftLauncher.py
	python -m autopep8 --in-place MyMinecraftLauncher.py

reset:
	rm -r "${LOCALAPPDATA}\MyMinecraftLauncher"

.PHONY: run fmt reset
