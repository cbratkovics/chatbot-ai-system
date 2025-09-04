import click
from . import __version__


def get_version():
    return __version__


def run_server(host="0.0.0.0", port=8000, reload=False):
    import uvicorn

    uvicorn.run("chatbot_ai_system.server.main:app", host=host, port=port, reload=reload)


def run_demo():
    print("Running demo...")
    run_server()


def run_benchmark(requests=100):
    print(f"Running benchmarks with {requests} requests...")
    import subprocess

    subprocess.run(["python3", "benchmarks/run_all_benchmarks.py", "--requests", str(requests)])


@click.group()
def cli():
    pass


@cli.command()
@click.option("--format", default="text", type=click.Choice(["text", "json"]))
def version(format):
    if format == "json":
        import json as j

        click.echo(j.dumps({"version": get_version()}))
    else:
        click.echo(f"v{get_version()}")


@cli.command()
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=8000)
@click.option("--reload", is_flag=True)
def serve(host, port, reload):
    run_server(host, port, reload)


@cli.command()
def demo():
    run_demo()


@cli.command()
@click.option("--requests", default=100, type=int)
def bench(requests):
    run_benchmark(requests)


if __name__ == "__main__":
    cli()
