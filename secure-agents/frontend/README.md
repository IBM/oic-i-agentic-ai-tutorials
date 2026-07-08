# FastAPI Project - Frontend

The frontend is built with [Vite](https://vitejs.dev/), [React](https://reactjs.org/), [TypeScript](https://www.typescriptlang.org/), [TanStack Query](https://tanstack.com/query), [TanStack Router](https://tanstack.com/router), [Carbon](https://carbondesignsystem.com/) and [Carboncn UI](https://www.carboncn.dev/).

## Install dependencies

Note: you might need to change your node version with nvm.
you can get nvm [here](https://github.com/nvm-sh/nvm#installing-and-updating)

```bash
cd frontend
nvm install # this will install the node version specified in .nvmrc
nvm use
```

Install the dependencies:

```bash
npm install
```

## Frontend development

_Note: for more detailed tips, e.g. on how to **create a new page**, see the tutorials [here](https://github.ibm.com/client-engineering-dach/full-stack-cen-template-tutorials/tree/main/full-stack-tutorial-watsonx-chat)_

The frontend will be started in development mode with hot reloading, inside the Docker Compose stack, so you don't have to worry about the correct node version or other dependencies.

```bash
docker compose watch
```

Open your browser at http://localhost:5173/

### (optional ) Using the Local Frontend Dev Server

Should you still want to use the local dev server, you can do so by following these steps:

```bash
# Stop the frontend container if running in Docker
docker compose stop frontend

cd frontend
npm run dev
```

Open your browser at http://localhost:5173/

## Generate Client

### Automatically

- Activate the backend virtual environment.
- From the top level project directory, run the script:

```bash
./scripts/generate-client.sh
```

- Commit the changes.

### Manually

- Start the Docker Compose stack.

- Download the OpenAPI JSON file from `http://localhost/api/v1/openapi.json` and copy it to a new file `openapi.json` at the root of the `frontend` directory.

- To simplify the names in the generated frontend client code, modify the `openapi.json` file by running the following script:

```bash
node modify-openapi-operationids.js
```

- To generate the frontend client, run:

```bash
npm run generate-client
```

- Commit the changes.

Notice that everytime the backend changes (changing the OpenAPI schema), you should follow these steps again to update the frontend client.

## Code Structure

The frontend code is structured as follows:

- `frontend/src` - The main frontend code.
- `frontend/src/assets` - Static assets.
- `frontend/src/client` - The generated OpenAPI client.
- `frontend/src/components` - The different components of the frontend.
- `frontend/src/hooks` - Custom hooks.
- `frontend/src/routes` - The different routes of the frontend which include the pages.

## Using a Remote API

If you want to use a remote API, you can set the environment variable `VITE_API_URL` to the URL of the remote API. For example, you can set it in the `frontend/.env` file:

```env
VITE_API_URL=https://api.my-domain.example.com
```

Then, when you run the frontend, it will use that URL as the base URL for the API.

## End-to-End Testing with Playwright

The frontend includes initial end-to-end tests using Playwright. To run the tests, you need to have the Docker Compose stack running. Start the stack with the following command:

```bash
docker compose up -d --wait backend
```

Then, you can run the tests with the following command:

```bash
npx playwright test
```

You can also run your tests in UI mode to see the browser and interact with it running:

```bash
npx playwright test --ui
```

To stop and remove the Docker Compose stack and clean the data created in tests, use the following command:

```bash
docker compose down -v
```

To update the tests, navigate to the tests directory and modify the existing test files or add new ones as needed.

For more information on writing and running Playwright tests, refer to the official [Playwright documentation](https://playwright.dev/docs/intro).

### Removing the frontend

If you are developing an API-only app and want to remove the frontend, you can do it easily:

- Remove the `./frontend` directory.

- In the `docker-compose.yml` file, remove the whole service / section `frontend`.

Done, you have a frontend-less (api-only) app. 🤓

---

If you want, you can also remove the `FRONTEND` environment variables from:

- `.env`
- `./scripts/*.sh`

But it would be only to clean them up, leaving them won't really have any effect either way.
