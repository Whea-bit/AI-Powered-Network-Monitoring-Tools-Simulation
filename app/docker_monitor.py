import docker

client = docker.from_env()

def get_containers():
    containers = []

    for c in client.containers.list():
        containers.append({
            "id": c.short_id,
            "name": c.name,
            "status": c.status
        })

    return containers
