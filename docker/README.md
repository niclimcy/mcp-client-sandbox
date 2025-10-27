### Running in Docker

The application's architecture looks something like this:

Client -- (inits) --> Server Manager -- (spawns) --> Server (stdio/http) processes.

For stdio servers, the client must write to the server's stdin, and read from the server's stdout.
We also want to isolate the server from its client, such that the server should not be aware of the client.

There are two ways to run this application setup.

1. Docker outside of Docker (DooD) - Running the client and server in two separate sibling containers under one host machine's Docker daemon.
2. Docker in Docker (DinD) - Running the client in a container, and running the server in a container, inside the client's Docker container.

### Method 1: Docker outside of Docker (DooD)

Requirements

1. Client must still be the own spawning the server processes.
2. Client and server must be in separate containers, under the same host system.
3. Client must be able to read and write from stdio of the server
4. Server should not be aware of a client

Explanation:
When running the client container, we mount the host system's Docker socket onto the client's container. This essentially overrides the client container's original Docker daemon and injects it with the host system's. This way, the client code can remain agnostic of how the server container is being deployed (Whether it is DooD or DinD). When the 'image' property is specified in the server's stdio server config, the server manager will wrap the original command with Docker, running the server process inside a Docker container. The client reads/write to/from the stdio of the Docker wrapper process, which acts as a proxy that passes the IO to and from the actual server process.

Build (from the root folder):

```bash
docker build -t mcp-client-monitoring -f ./docker/Dockerfile .
```

Run:

```bash
docker run -d \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v $(pwd):/app \
    -e GOOGLE_API_KEY="<google_api_key>" \
    mcp-client-monitoring
```

```bash
docker exec -it <container_id> /bin/sh
```

While inside the container, run the main command

```bash
uv run main.py
```
