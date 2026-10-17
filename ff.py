import re
import requests
import os
import time
def clear_terminal():
    os.system("cls")




INPUT_FILE = "input.txt"
CHECKED_FILE = "checked.txt"
OUTPUT_FILE = "output.txt"

checked_ids = set()

valid_count = 0
duplicate_count = 0
nottr = 0


# 1) تحميل IDs اللي اتسجلت قبل كده في checked.txt
# try:
#     with open(CHECKED_FILE, "r", encoding="utf-8") as f:
#         for line in f:
#             line = line.strip()
#             # نتأكد إن السطر رقم بس (ID سليم)
#             if line.isdigit():
#                 checked_ids.add(line)
# except FileNotFoundError:
#     # لو مفيش ملف checked.txt لسه، نكمل عادي
#     pass


# 2) قراءة input.txt ومعالجة كل سطر
with open(INPUT_FILE, "r", encoding="utf-8") as f_in, \
     open(CHECKED_FILE, "a", encoding="utf-8") as f_checked, \
     open(OUTPUT_FILE, "a", encoding="utf-8") as f_out:

    for line in f_in:
        line = line.strip()
        if not line:
            continue
        clear_terminal()
        print(f"✔ Valid: {valid_count}   ↻ Duplicates: {duplicate_count}   ✖ Not matched: {nottr}")
        time.sleep(0.2)

        match = re.search(r"c_user=(\d+)", line)
        if not match:
            continue

        user_id = match.group(1)

        # user_id = line.split(':')[0]

        if user_id in checked_ids:
            duplicate_count += 1
            continue

        try:
            headers = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9',
    'origin': 'https://2fa.cn',
    'priority': 'u=1, i',
    'referer': 'https://2fa.cn/',
    'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'cross-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',}
            params = {'redirect': 'false',}
            response = requests.get(f'https://graph.facebook.com/{user_id}/picture', params=params, headers=headers)
            if "height" in response.text:
                valid_count +=1
                # f_out.write(f"{user_id}|123123yy|{line}\n")
                f_out.write(f"{line}\n")
                # f_out.write(user_id + "\n")
                # f_checked.write(user_id + "\n")
                checked_ids.add(user_id)
            else:
                nottr += 1
                continue
        except:
            continue



        

print("\n----------- Processing Summary -----------")
print(f"✔️  Valid IDs          : {valid_count}")
print(f"🔁  Duplicate IDs      : {duplicate_count}")
print(f"❌  Invalid/Unmatched  : {nottr}")
print("------------------------------------------\n")
