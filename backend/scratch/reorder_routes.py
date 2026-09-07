import re

with open('app/api/routes/passenger.py', 'r') as f:
    content = f.read()

# find the entire search_services function
# it starts at @router.get("/api/passenger/services/search" and ends before @router.get("/api/passenger/services/{service_id}/live" or some other endpoint

search_start = content.find('@router.get("/api/passenger/services/search"')
if search_start == -1:
    print("Could not find search_services start")
    exit(1)

# Find the next @router.get after search_start + 10
next_router = content.find('@router.get(', search_start + 10)
if next_router == -1:
    print("Could not find next route")
    exit(1)

search_block = content[search_start:next_router]
content_without_search = content[:search_start] + content[next_router:]

target = content_without_search.find('@router.get("/api/passenger/services/{service_id}"')
if target == -1:
    print("Could not find get_service_details")
    exit(1)

final_content = content_without_search[:target] + search_block + content_without_search[target:]

with open('app/api/routes/passenger.py', 'w') as f:
    f.write(final_content)
print("Moved successfully")
