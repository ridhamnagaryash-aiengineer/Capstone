import os
from dotenv import load_dotenv
load_dotenv()

from pymilvus import connections, Collection

uri = os.getenv("MILVUS_URI")
token = os.getenv("MILVUS_API_KEY")

connections.connect("default", uri=uri, token=token)

collections = [
    "hrms_hr_policy",
    "hrms_payroll",
    "hrms_it_support",
    "hrms_facilities",
    "hrms_uncategorized",
]

print("\n---- VECTOR COUNTS ----")
for name in collections:
    try:
        col = Collection(name)
        col.load()
        print(name, ":", col.num_entities)
    except Exception as e:
        print(name, "error:", e)
