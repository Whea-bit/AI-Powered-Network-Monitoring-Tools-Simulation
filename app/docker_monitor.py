import docker

def get_containers():
    try:
        client = docker.from_env()

        containers = []

        for c in client.containers.list():
            containers.append({
                "id": c.short_id,
                "name": c.name,
                "status": c.status
            })

        return containers

    except Exception as e:
        return [{"error": str(e)}]

