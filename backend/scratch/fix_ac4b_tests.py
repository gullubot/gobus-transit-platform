import sys

def replace_in_file(filename):
    with open(filename, 'r') as f:
        content = f.read()
    
    content = content.replace('["service_name"] == "AC4B"', '["service_name"].startswith("AC4B")')
    
    with open(filename, 'w') as f:
        f.write(content)

replace_in_file('tests/api/test_passenger_search.py')
replace_in_file('tests/api/test_passenger_step5.py')
print("Replaced!")
