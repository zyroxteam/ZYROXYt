import requests, urllib3
urllib3.disable_warnings()

VID="dQw4w9WgXcQ"
H={"Origin":"https://frame.y2meta-uk.com","Referer":"https://frame.y2meta-uk.com/","Accept":"application/json","User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}

# Step 1: sanity key
try:
    r=requests.get(f"https://cnv.cx/v2/sanity/key?id={VID}",headers=H,timeout=15,verify=False)
    print("STEP1 key status:",r.status_code)
    j=r.json()
    key=j.get("key")
    print("key:",key[:60] if key else key)
except Exception as e:
    print("STEP1 FAIL:",e); raise SystemExit

# Step 2: converter
fd={"link":f"https://youtu.be/{VID}","format":"mp4","audioBitrate":"128","videoQuality":"720","filenameStyle":"pretty","vCodec":"h264"}
H2={"Origin":"https://frame.y2meta-uk.com","Referer":"https://frame.y2meta-uk.com/","Content-Type":"application/x-www-form-urlencoded","Accept":"*/*","key":key,"User-Agent":"Mozilla/5.0"}
try:
    r2=requests.post("https://cnv.cx/v2/converter",data=fd,headers=H2,timeout=30,verify=False)
    print("STEP2 converter status:",r2.status_code)
    print("STEP2 body:",r2.text[:400])
except Exception as e:
    print("STEP2 FAIL:",e)
