import re
import requests

PAGE_URL = "https://www.incois.gov.in/oceanservices/rsmc_download.jsp"

# 1. Find latest WW3 filename
response = requests.get(PAGE_URL, timeout=30)
response.raise_for_status()

matches = re.findall(
    r"rsmc_combined_ww3_(\d{8})\.nc",
    response.text
)

if not matches:
    raise RuntimeError("No WW3 file found.")

latest = max(matches)
filename = f"rsmc_combined_ww3_{latest}.nc"

file_url = (
    f"https://www.incois.gov.in/thredds/fileServer/"
    f"osf/ww3/{filename}"
)

print("Latest file:", filename)
print("Checking file...")

# 2. Check that the file exists WITHOUT downloading it
head = requests.head(
    file_url,
    allow_redirects=True,
    timeout=30
)

print("HTTP status:", head.status_code)

if head.status_code == 200:
    print("INCOIS file is available.")

    size = head.headers.get("Content-Length")

    if size:
        size_gb = int(size) / (1024 ** 3)
        print(f"Remote file size: {size_gb:.2f} GB")
    else:
        print("Remote file size: not provided")

else:
    print("File could not be verified.")

print("URL:")
print(file_url)