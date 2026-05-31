from setuptools import setup

setup(
    name="essaide",
    version="0.1.0",
    description="EssaIDE Custom Terminal IDE",
    py_modules=["main"],
    install_requires=[
        "textual[syntax]>=0.81.0",
        "rich==13.7.1",
        "requests==2.32.3"
    ],
    entry_points={
        "console_scripts": [
            "essa-ide=main:run",
        ],
    },
)
