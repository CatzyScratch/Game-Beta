import pygame as py
import sys

py.init()

#Window Setup
WindowW, WindowH = 480, 360
Window = py.display.set_mode((WindowW, WindowH))
WindowC, WindowT, Tick = py.display.set_caption("Horror Game"), py.time.Clock(), 30

#Map Setup
TileS = 56
Coli = {0, 1, 2, 3, 4, 5, 6, 7, 13, 17, 18, 19}
Trans = {12}

#General purpose file loader
def loadr(x):
    with open(x) as f:
        return f.readlines()

Map = loadr("assets/map files/1.tmf")
Map = [[int(v) for v in line.split()] for line in Map]

Texs = [
    py.image.load(path.strip()).convert_alpha()
    for path in loadr("assets/map files/textures.texf")
]

'''
print("Textures loaded:", len(Texs))
print("Map:", Map)
print("Highest tile ID:", max(max(row) for row in Map))
'''

#TileMap Drawer
def drawm(x, y):
    for rowi, row in enumerate(y):
        for coli, tilet in enumerate(row):

            tx = coli * TileS
            ty = rowi * TileS
            tilec = Texs[tilet]
            x.blit(
                py.transform.scale(tilec, (TileS, TileS)),
                (tx, ty)
            )

#Rect setup
Plr = py.Rect(0, 0, 56, 56)
PlrM = False
PlrPX, PlrPY = Plr.x, Plr.y
PlrMD = 0
PlrD = "None"
PlrImg = py.image.load(f"assets/character images/Player-Idle-Front.png")
PlrImg = py.transform.scale(PlrImg, (TileS, TileS))

#Tile collision handler
def coli(x, y):
    if x < 0 or y < 0 or y >= len(Map) or x >= len(Map[y]):
        return True
    return Map[y][x] in Coli

def mov():
    global PlrM, PlrPX, PlrPY, PlrMD, PlrD, WindowW, WindowH, PlrImg
    
    k = py.key.get_pressed()
    
    #Key detection
    x, y = Plr.x // TileS, Plr.y // TileS

    if not PlrM and Map[y][x] in Trans:
        next_map()
        return
    
    if not PlrM == True:
        PlrPX, PlrPY = Plr.x, Plr.y

        if k[py.K_LEFT] and not coli(x-1, y):
            PlrD = "LEFT"
            PlrMD = -4
            PlrM = True

        if k[py.K_UP] and not coli(x, y-1):
            PlrD = "UP"
            PlrMD = -4
            PlrM = True

        if k[py.K_DOWN] and not coli(x, y+1):
            PlrD = "DOWN"
            PlrMD = 4
            PlrM = True
            
        if k[py.K_RIGHT] and not coli(x+1, y):
            PlrD = "RIGHT"
            PlrMD = 4
            PlrM = True

    #NES Style glide (Very bad implementation ik)
    if PlrM == True:
        if PlrD == "RIGHT" or PlrD == "LEFT":
            
            if PlrD == "RIGHT":
                if not PlrPX + 56 > 480 - 56:
                    if not Plr.x == PlrPX + 56:
                        Plr.x += PlrMD
                    else: PlrM = False;PlrPX, PlrPY = Plr.x, Plr.y
                else: PlrM = False;PlrPX, PlrPY = Plr.x, Plr.y
                        
            elif PlrD == "LEFT":
                if not PlrPX - 56 < 0:
                    if not Plr.x == PlrPX - 56:
                        Plr.x += PlrMD
                    else: PlrM = False;PlrPX, PlrPY = Plr.x, Plr.y
                else: PlrM = False;PlrPX, PlrPY = Plr.x, Plr.y

        elif PlrD == "UP":
            if not PlrPY - 56 < 0:
                if not Plr.y == PlrPY - 56:
                    Plr.y += PlrMD
                else: PlrM = False;PlrPX, PlrPY = Plr.x, Plr.y
            else: PlrM = False;PlrPX, PlrPY = Plr.x, Plr.y

        elif PlrD == "DOWN":
            if not PlrPY + 56 > 360 - 56:
                if not Plr.y == PlrPY + 56:
                    Plr.y += PlrMD
                else: PlrM = False;PlrPX, PlrPY = Plr.x, Plr.y
            else: PlrM = False;PlrPX, PlrPY = Plr.x, Plr.y
      
def upd():
    global Tiles, TileS, Map
    mov()
    
    #Events
    for e in py.event.get():
        if e.type == py.QUIT or (e.type == py.KEYDOWN and e.key == py.K_ESCAPE):
            py.quit()
            sys.exit()
            
    Window.fill((255, 255, 255))
    drawm(Window, Map)
    Window.blit(PlrImg, Plr)
    #py.draw.rect(Window, ((0, 0, 0)), Plr)
    py.display.update()
    WindowT.tick(Tick)
    WindowC = py.display.set_caption(f"Horror Game | FPS: {WindowT.get_fps():.2f}")
          
while True:
    upd()
