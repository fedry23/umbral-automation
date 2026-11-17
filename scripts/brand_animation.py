"""Original animated architecture, atmosphere and typography; no stock assets.

Every frame projects geometry from a moving camera. Fog, particles, door angle
and illumination evolve independently. CPU-only deterministic rendering.
"""
import math
from pathlib import Path
import subprocess
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scripts.brand_cards import font, fit_title

W, H, FPS = 720, 1280, 24


@lru_cache(maxsize=2)
def stone(material="stone"):
    """Original mineral texture, fixed in world space rather than screen noise."""
    rng = np.random.default_rng(651)
    y,x = np.mgrid[:256,:256]
    noise = rng.normal(0,14,(256,256))
    cloud = np.asarray(Image.fromarray(rng.integers(30,230,(16,16),dtype=np.uint8)).resize((256,256),Image.Resampling.BICUBIC),dtype=float)
    grain = 95 + noise + cloud*.45 + 8*np.sin(x*.27+np.sin(y*.12))
    mortar = (y%64 < 3) | ((x + (y//64%2)*64)%128 < 3)
    if material == "stone":
        grain[mortar] *= .38
    else:
        grain = 115 + noise*.6 + 22*np.sin(x*.35 + np.sin(y*.008)*3) + 9*np.sin(x*1.7+y*.015)
    return Image.fromarray(np.uint8(np.clip(grain,0,255)))


@lru_cache(maxsize=1)
def static_layers():
    """Immutable layers reused without changing a single rendered pixel."""
    yy, xx = np.mgrid[:H:4,:W:4].astype(np.float32)
    fog_envelope = np.exp(-((yy-H*.76)/(H*.26))**2)
    vignette = np.clip(1 - .5*((np.arange(W)[None,:]-W/2)/(W/2))**2, .4,1)
    grain = np.random.default_rng(902).normal(0,1.5,(H,W))
    stains = np.sin(np.arange(H)[:,None]*.017 + np.sin(np.arange(W)[None,:]*.023))*1.8
    surface = (grain+stains)[:,:,None]
    particles = np.random.default_rng(850).random((65,4))
    for array in (yy,xx,fog_envelope,vignette,surface,particles):
        array.setflags(write=False)
    return yy,xx,fog_envelope,vignette,surface,particles


def frame(story, kind, t, duration):
    p = min(1.0, t / duration)
    closing = kind == 'outro'
    camera = -1.8 - 1.8 * p if closing else -3.8 + 1.6 * p
    def project(x, y, z):
        scale = 690 / (z - camera)
        return (W / 2 + x * scale, H * .52 - y * scale)
    image = Image.new('RGB', (W, H), (5, 7, 12))
    d = ImageDraw.Draw(image)
    tint = (85, 150, 205) if closing else (240, 34, 31)
    opening = max(0, 1 - p * 1.4) if closing else .16 + .15 * p
    flicker = .92 + .04 * math.sin(t * 2.1) + .025 * math.sin(t * 7.3)
    def poly(points, fill, outline=None, width=1, textured=True):
        coords=[project(*q) for q in points]
        d.polygon(coords, fill=fill, outline=outline, width=width)
        if not textured or len(points)!=4:
            return
        left=max(0,int(min(q[0] for q in coords))); right=min(W,int(max(q[0] for q in coords))+1)
        top=max(0,int(min(q[1] for q in coords))); bottom=min(H,int(max(q[1] for q in coords))+1)
        if right<=left or bottom<=top:
            return
        local=[(x-left,y-top) for x,y in coords]
        rows=[]; values=[]
        for (x,y),(u,v) in zip(local,[(0,256),(0,0),(256,0),(256,256)]):
            rows.extend([[x,y,1,0,0,0,-u*x,-u*y],[0,0,0,x,y,1,-v*x,-v*y]])
            values.extend([u,v])
        try:
            coeff=np.linalg.solve(rows,values)
        except np.linalg.LinAlgError:
            return
        tex=stone("wood" if textured == "wood" else "stone").transform((right-left,bottom-top),Image.Transform.PERSPECTIVE,coeff,Image.Resampling.BILINEAR)
        rgb=np.asarray(tex,dtype=float)[:,:,None]/150*np.array(fill)[None,None,:]
        mask=Image.new('L',tex.size)
        ImageDraw.Draw(mask).polygon(local,fill=255)
        image.paste(Image.fromarray(np.uint8(np.clip(rgb,0,255))),(left,top),mask)
    # Floor and ceiling, receding stone ribs and mortar lines provide parallax.
    poly([(-5,-1.8,0),(5,-1.8,0),(5,-1.8,35),(-5,-1.8,35)], (16,17,20))
    for z in (reversed(range(0, 36, 3)) if closing else (8,4,0)):
        tone = int(22 * (1 - z / 45))
        for side in (-1,1):
            poly([(side*2,-1.8,z),(side*2,2.5,z),(side*2,2.5,z+2.6),(side*2,-1.8,z+2.6)],
                 (tone,tone+2,tone+5), (tone+9,tone+10,tone+12), 2)
            poly([(side*1.85,-1.8,z),(side*1.85,2.5,z),(side*2,2.5,z), (side*2,-1.8,z)],
                 (tone+7,tone+8,tone+10))
        d.line([project(-2,-1.8,z),project(2,-1.8,z)], fill=(34,33,35), width=2)
        for x in (-1,0,1):
            d.line([project(x,-1.8,z),project(x,-1.8,z+3)], fill=(24,24,28), width=1)
    # Monumental independent portal; closing door rotates around its hinge.
    z = 5 if closing else 1.7
    for n in range(5):
        a = 1.03 + n * .09
        b = 1.8 + n * .10
        poly([(-a,-1.8,z-n*.05),(-a,b,z-n*.05),(a,b,z-n*.05),(a,-1.8,z-n*.05)],
             (26+n*3,25+n*2,30+n*2), (50,46,49), 2)
    light = tuple(int(c * min(1, opening*2.8) * flicker) for c in tint)
    poly([(-1,-1.8,z),(-1,1.8,z),(1,1.8,z),(1,-1.8,z)], light, textured=False)
    angle = opening * 1.2
    edge_x = -1 + 2 * math.cos(angle)
    edge_z = z + 2 * math.sin(angle)
    poly([(-1,-1.8,z),(-1,1.8,z),(edge_x,1.8,edge_z),(edge_x,-1.8,edge_z)],
         (12,15,21) if closing else (19,10,13), (63,57,61), 3, textured="wood")
    for yy in (-1.45,-.1,.25,1.45):
        d.line([project(-.85,yy,z-.02),project(edge_x-.12,yy,edge_z-.02)], fill=(44,37,40), width=2)
    knob = project(edge_x-.2, -.05, edge_z-.05)
    d.ellipse((knob[0]-4,knob[1]-4,knob[0]+4,knob[1]+4), fill=(132,113,88))
    # Soft light cones and reflected colour, independently pulsing.
    glow = Image.new('RGB',(W,H))
    gd = ImageDraw.Draw(glow)
    origin = project(.95,-1.75,z)
    gd.polygon([origin,(W*.9,H),(W*.28,H)], fill=tuple(int(c*opening*.34) for c in tint))
    top_light = project(.98,1.78,z)
    gd.line([top_light,origin],fill=tuple(int(c*opening*.6) for c in tint),width=38)
    glow = glow.filter(ImageFilter.GaussianBlur(30))
    arr = np.asarray(image).astype(np.float32) + np.asarray(glow)
    # Layered moving fog: different velocities and scales imply depth.
    yy, xx, fog_envelope, vignette, surface, particles = static_layers()
    fog = np.zeros_like(xx)
    for k in range(1,5):
        fog += (np.sin(xx/(40*k)+t*(.16+k*.08)+np.sin(yy/(60+k*20)-t*.12))
                * np.cos(yy/(25*k)-t*.08*k)) / (k+2)
    fog = np.maximum(0,fog+.35) * fog_envelope
    fog_img = Image.fromarray(np.uint8(np.clip(fog*55,0,85))).resize((W,H),Image.Resampling.BILINEAR)
    fog_arr = np.asarray(fog_img).astype(np.float32)
    arr += fog_arr[:,:,None] * np.array([.50,.65,.85] if closing else [.85,.43,.39])
    arr += surface
    arr *= vignette[:,:,None]
    image = Image.fromarray(np.uint8(np.clip(arr,0,255)))
    d = ImageDraw.Draw(image)
    for x,y,speed,size in particles:
        px = (x*W + math.sin(t*.2+x*8)*16) % W
        py = (y*H - t*(7+speed*18)) % H
        c = int(45+70*size)*(.4+opening)
        d.ellipse((px,py,px+1+size*2,py+1+size*2),fill=tuple(min(255,int(c*v)) for v in ([.6,.8,1] if closing else [1,.5,.4])))
    # Typography appears separately from scenery, keeping subtitle band clear.
    overlay = Image.new('RGBA',(W,H))
    od = ImageDraw.Draw(overlay)
    alpha = min(1,t/.65) if not closing else min(1,max(0,(p-.32)*4))
    def center(text,y,f,color):
        width = od.textbbox((0,0),text,font=f)[2]
        od.text(((W-width)/2,y),text,font=f,fill=(*color,int(255*alpha)),stroke_width=1,stroke_fill=(0,0,0,int(200*alpha)))
    center('UMBRAL', 165+int((1-alpha)*16), font(86), (233,224,218))
    if not closing:
        center('HISTORIA '+str(story['episode_number']).zfill(2),290,font(27),(231,93,87))
        style, lines = fit_title(od, story['title'], max_width=610)
        for i,line in enumerate(lines):
            center(line,730+i*(style.size+12),style,(239,231,225))
    image = Image.alpha_composite(image.convert('RGBA'),overlay).convert('RGB')
    fade = min(1,t/.35)
    if closing:
        fade *= min(1,max(0,(duration-t)/.75))
    return Image.fromarray(np.uint8(np.asarray(image).astype(float)*fade))


def render_brand(story, kind, duration, out):
    path = Path(out) / (kind + '_animation.mp4')
    cmd = ['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo',
           '-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
           '-an','-c:v','libx264','-threads','2','-preset','veryfast','-crf','20',
           '-pix_fmt','yuv420p','-movflags','+faststart',str(path)]
    proc = subprocess.Popen(cmd,stdin=subprocess.PIPE)
    try:
        for i in range(math.ceil(duration*FPS)):
            pic = frame(story,kind,i/FPS,duration)
            proc.stdin.write(pic.tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError('FFmpeg no pudo renderizar el escenario de marca')
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    return path
