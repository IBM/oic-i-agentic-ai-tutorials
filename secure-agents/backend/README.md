# FastAPI Project - Backend

## Requirements

- [Docker](https://www.docker.com/).
- [uv](https://docs.astral.sh/uv/) for Python package and environment management.

## Docker Compose

Start the local development environment with Docker Compose following the guide in [../.docs/development.md](../.docs/development.md).

## Backend Development

_Note: for more detailed tips, e.g. on how to **create a new API endpoint**, see the tutorials [here](https://github.ibm.com/client-engineering-dach/full-stack-cen-template-tutorials/tree/main/full-stack-tutorial-watsonx-chat)_

By default, the dependencies are managed with [uv](https://docs.astral.sh/uv/), go there and install it.

<!-- TODO: choose correct python version -->

From `./backend/` you can install all the dependencies with:

```console
$ uv sync
```

Then you can activate the virtual environment with:

```console
$ source .venv/bin/activate
```

Make sure your editor is using the correct Python virtual environment, with the interpreter at `backend/.venv/bin/python`.

_(To do that, press `Cmd+Shift+P` and search for `Python: Select Interpreter` --> Click on `Enter interpreter path` --> Enter interpreter path `backend/.venv/bin/python`.)_

Modify or add SQLModel models for data and SQL tables in `./backend/app/tables.py`, API endpoints in `./backend/app/api/`, CRUD (Create, Read, Update, Delete) utils in `./backend/app/crud.py`.

## VS Code

There are already configurations in place to run the backend through the VS Code debugger, so that you can use breakpoints, pause and explore variables, etc.

Make sure your venv is activated and your Python interpreter is set correctly, explained in the previous section ⬆️.

The setup is also already configured so you can run the tests through the VS Code Python tests tab.

## Docker Compose

During development, you can change Docker Compose settings that will only affect the local development environment in the file `docker-compose.yml`.

The changes to that file only affect the local development environment, not the production environment. So, you can add "temporary" changes that help the development workflow.

For example, the directory with the backend code is synchronized in the Docker container, copying the code you change live to the directory inside the container. That allows you to test your changes right away, without having to build the Docker image again. It should only be done during development, for production, you should build the Docker image with a recent version of the backend code. But during development, it allows you to iterate very fast.

There is also a command override that runs `fastapi run --reload` instead of the default `fastapi run`. It starts a single server process (instead of multiple, as would be for production) and reloads the process whenever the code changes. Have in mind that if you have a syntax error and save the Python file, it will break and exit, and the container will stop. After that, you can restart the container by fixing the error and running again:

```console
$ docker compose watch
```

To get inside the container with a `bash` session you can start the stack with:

```console
$ docker compose watch
```

and then in another terminal, `exec` inside the running container:

```console
$ docker compose exec backend bash
```

You should see an output like:

```console
root@7f2607af31c3:/app#
```

that means that you are in a `bash` session inside your container, as a `root` user, under the `/app` directory, this directory has another directory called "app" inside, that's where your code lives inside the container: `/app/app`.

There you can use the `fastapi run --reload` command to run the debug live reloading server.

```console
$ fastapi run --reload app/main.py
```

...it will look like:

```console
root@7f2607af31c3:/app# fastapi run --reload app/main.py
```

and then hit enter. That runs the live reloading server that auto reloads when it detects code changes.

Nevertheless, if it doesn't detect a change but a syntax error, it will just stop with an error. But as the container is still alive and you are in a Bash session, you can quickly restart it after fixing the error, running the same command ("up arrow" and "Enter").

...this previous detail is what makes it useful to have the container alive doing nothing and then, in a Bash session, make it run the live reload server.

## Backend tests

To test the backend run:

```console
$ bash ./scripts/test.sh
```

The tests run with Pytest, modify and add tests to `./backend/app/tests/`.

If you use GitHub Actions the tests will run automatically.

### Test running stack

If your stack is already up and you just want to run the tests, you can use:

```bash
docker compose exec backend bash scripts/tests-start.sh
```

That `/app/scripts/tests-start.sh` script just calls `pytest` after making sure that the rest of the stack is running. If you need to pass extra arguments to `pytest`, you can pass them to that command and they will be forwarded.

For example, to stop on first error:

```bash
docker compose exec backend bash scripts/tests-start.sh -x
```

### Test Coverage

When the tests are run, a file `htmlcov/index.html` is generated, you can open it in your browser to see the coverage of the tests.

## Migrations

Whenever your models in `./backend/app/tables.py` are changed, you need to create a migration to update the database schema. This is handled with Alembic.

### Prerequisites for migrations

1. Make sure your virtual environment is activated:

   ```bash
   cd backend
   source .venv/bin/activate
   ```

2. Ensure your Docker Compose stack is running so the database is available:

   ```bash
   docker compose watch
   ```

### Creating and applying migrations

After changing a model (for example, adding a column), create a revision:

```bash
cd backend
alembic revision --autogenerate -m "Add column last_name to User model"
```

This will generate new migration files in the `./backend/app/alembic/versions/` directory.

To apply the migration to your local database:

```bash
alembic upgrade head
```

### Important notes

- Always commit migration files to your repository. When deployed to production, these migrations will be automatically applied to your production database on container startup.
- If you don't want to use migrations at all, uncomment the lines in `./backend/app/core/db.py` that contain:

  ```python
  SQLModel.metadata.create_all(engine)
  ```

  and comment the line in `scripts/prestart.sh` that contains:

  ```console
  $ alembic upgrade head
  ```

- If you want to start with a clean migration history, you can remove all files under `./backend/app/alembic/versions/` and create your first migration as described above.
