from setuptools import find_packages, setup

setup(
    name="chatbot-ai-system",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11",
)
