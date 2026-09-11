import subprocess, sys, statistics
W,H=64,36; FPS=60; DUR=3
cmd=["ffmpeg","-loglevel","error","-f","x11grab","-framerate",str(FPS),
     "-video_size","1280x720","-i",":95+0,0","-vf",f"scale={W}:{H},format=gray",
     "-t",str(DUR),"-f","rawvideo","-"]
raw=subprocess.run(cmd,capture_output=True).stdout
fs=W*H
nf=len(raw)//fs
frames=[raw[i*fs:(i+1)*fs] for i in range(nf)]
diffs=[]
for i in range(1,nf):
    a,b=frames[i-1],frames[i]
    diffs.append(sum(abs(a[j]-b[j]) for j in range(fs))/fs)
# periodicity: how "spiky" is the motion? CV and count of near-zero frames
mean=statistics.mean(diffs); sd=statistics.pstdev(diffs)
nz=sum(1 for d in diffs if d<0.05)   # frames with essentially no change
print(f"frames={nf} mean_diff={mean:.3f} sd={sd:.3f} CV={sd/mean if mean else 0:.2f} near_zero_frames={nz}/{len(diffs)}")
