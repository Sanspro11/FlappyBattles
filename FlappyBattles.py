import pygame 
import random
import socket
import threading
import json
import base64
import secrets
import datetime
from sys import exit

from tcp_by_size import send_with_size ,recv_by_size # type: ignore (this is for pylance error detection)
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

pygame.init()
clock = pygame.time.Clock()

width = 1280
height = 720
window = pygame.display.set_mode((width,height))
pygame.display.set_caption('FlappyBattles')
pygame.display.set_icon(pygame.image.load('assets/Icon.png'))

background = pygame.image.load("assets/Background.png").convert() # convert for faster bliting (like x6 faster)
ground = pygame.image.load("assets/Ground.png").convert()
gun = pygame.image.load("assets/Weapons/Gun.png").convert_alpha() # same as convert but for images with trasparency
gunLeft = pygame.transform.flip(gun,True,False).convert_alpha()
bubble = pygame.image.load("assets/Birds/Bubble.png").convert_alpha()
logo = pygame.image.load("assets/Logo.png").convert_alpha()
longButton = pygame.image.load("assets/LongButton.png").convert_alpha()
shortButton = pygame.image.load("assets/ShortButton.png").convert_alpha()
bird_image =  pygame.image.load("assets/Birds/Bird.png").convert_alpha()
bird_hurt = pygame.image.load("assets/Birds/birdhurt.png").convert_alpha()
bird_hurt_back = pygame.transform.flip(bird_hurt,True,False).convert_alpha() 
bird_back = pygame.transform.flip(bird_image,True,False).convert_alpha()
fist = pygame.image.load("assets/Weapons/fist.png").convert_alpha()
fistBack = pygame.transform.flip(fist,True,False).convert_alpha()
bulletImg = pygame.image.load("assets/Weapons/bullet.png").convert_alpha()
bulletBack = pygame.transform.flip(bulletImg,True,False).convert_alpha()

clients = []
threads = []
game_state = {'players': {}, 'menu': True, 'items': [], 'bullets': []}
colorsDict = {}
renderedChatMessages = []
bigRenderedChatMessages = []
ALLOWEDCHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!?@#$%^&*().,/ '

key = 'A'
rsaKey = None

name = ''
menu_error = ''

def flood_fill_image(image, x, y, color):
    width, height = image.get_size()
    new_image = image.copy()
    pixels = pygame.PixelArray(new_image)
    target_color = pixels[x, y]

    def fill(x, y):
        if (x < 0 or x >= width or y < 0 or y >= height or pixels[x, y] != target_color):
            return
        pixels[x, y] = color
        fill(x + 1, y)
        fill(x - 1, y)
        fill(x, y + 1)
        fill(x, y - 1)

    fill(x, y)
    del pixels
    return new_image



colorsDict['blue'] =  (flood_fill_image(bird_image, 10,7, (0,0,255)), 
                       flood_fill_image(bird_back, 20,7, (0,0,255)),
                       flood_fill_image(fist, 20,20, (0,0,255)),
                       flood_fill_image(fistBack, 20,20, (0,0,255))    )
colorsDict['red'] =   (flood_fill_image(bird_image, 10,7, (255,0,0)), 
                       flood_fill_image(bird_back, 20,7, (255,0,0)),
                       flood_fill_image(fist, 20,20, (255,0,0)),
                       flood_fill_image(fistBack, 20,20, (255,0,0))    )
colorsDict['green'] = (flood_fill_image(bird_image, 10,7, (0,255,0)), 
                       flood_fill_image(bird_back, 20,7, (0,255,0)),
                       flood_fill_image(fist, 20,20, (0,255,0)),
                       flood_fill_image(fistBack, 20,20, (0,255,0))    )
colorsDict['yellow']= (flood_fill_image(bird_image, 10,7, (255,255,0)), 
                       flood_fill_image(bird_back, 20,7, (255,255,0)),
                       flood_fill_image(fist, 20,20, (255,255,0)),
                       flood_fill_image(fistBack, 20,20, (255,255,0))    )




class Button:
    def __init__(self, x, y, text, function, long):
        self.x = x
        self.y = y
        self.text = text
        self.font = pygame.font.Font(None, 50)
        if long:
            self.rect = pygame.rect.Rect(x,y,longButton.get_width(),longButton.get_height())
            self.image = longButton
        else:
            self.rect = pygame.rect.Rect(x,y,shortButton.get_width(),shortButton.get_height())
            self.image = shortButton
        self.function = function

    def draw(self):
        window.blit(self.image,(self.x,self.y))
        text_surface = self.font.render(self.text, True, (255,255,255)) #white
        window.blit(text_surface,text_surface.get_rect(center=self.rect.center))

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)
    
    def function(self):
        self.function()

class TextBox:

    def __init__(self, x, y, w, h, text=''):
        self.rect = pygame.Rect(x, y, w, h)
        self.color = (0,0,0) # Black
        self.text = text
        self.active = False
        self.font = pygame.font.Font(None, h)


    def update(self,event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE: # delete character
                self.text = self.text[:-1]
            else:
                if len(self.text) < 30 and event.unicode in ALLOWEDCHARS:
                    self.text += event.unicode # type character
        txt_surface = self.font.render(self.text, True, self.color)
        width = max(100, txt_surface.get_width()+10)
        self.rect.w = width
        self.draw()

    def draw(self):
        txt_surface = self.font.render(self.text, True, self.color)
        window.blit(txt_surface, (self.rect.x+5, self.rect.y+5))
        pygame.draw.rect(window, self.color, self.rect, 3)

def print_text(text,x,y,size):
    window.blit(pygame.font.SysFont(None,size).render(text, True,(255,255,255)) , (x,y))

def render_text(text,size):
    return pygame.font.SysFont(None,size).render(text, True,(255,255,255))

def new_message(msg):
    if len(renderedChatMessages) > 10:
        del renderedChatMessages[0]
        del bigRenderedChatMessages[0]
    renderedChatMessages.append(render_text(msg,20))
    bigRenderedChatMessages.append(render_text(msg,49))

def send(socket,msg):
    send_with_size(socket,msg)
    prefix = f'Sent({len(msg)}) >> ' 
    print(prefix + (msg if len(msg) < 50 else f'{msg[:50]}...'))
    msg = prefix + str(msg)
    with open(f'Flappy-{name}.log', 'a') as file:
        file.write(str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')) + ' ' + msg + '\n') 

def recv(socket):
    response = recv_by_size(socket)
    prefix = f'Recv({len(response)}) << '
    print(prefix + (response if len(response) < 50 else f'{response[:50]}...'))
    msg = prefix + response    
    with open(f'Flappy-{name}.log', 'a') as file:
        file.write(str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')) + ' ' + msg + '\n') 
    return response

def clear_messages():
    renderedChatMessages.clear()
    bigRenderedChatMessages.clear()

def update():
    pygame.display.update()

def encrypt_message(message, key): # AES
    if type(key) != bytes:
        key = key.encode('utf-8')  
    key = key.ljust(32, b'\0')[:32]  
    
    cipher = AES.new(key, AES.MODE_CBC)
    ct_bytes = cipher.encrypt(pad(message.encode('utf-8'), AES.block_size))
    iv = base64.b64encode(cipher.iv).decode('utf-8')
    ct = base64.b64encode(ct_bytes).decode('utf-8')
    return iv + ct

def decrypt_message(encrypted_message, key): # AES
    if type(key) != bytes:
        key = key.encode('utf-8')
    key = key.ljust(32, b'\0')[:32]
    
    iv = base64.b64decode(encrypted_message[:24])
    ct = base64.b64decode(encrypted_message[24:])
    cipher = AES.new(key, AES.MODE_CBC, iv)
    pt = unpad(cipher.decrypt(ct), AES.block_size).decode('utf-8')
    return pt

def command(command):
    global game_state
    if command == '/ip':
        hostname=socket.gethostname()
        IP=socket.gethostbyname(hostname)
        
        new_message("Computer name:" + hostname)
        new_message("Ip:"+IP)
        return True # was a command
    return False #was not a command


def get_compacted_input(input):
    client_input = {'flapping': False, 'left': False, 'right': False, 'sprinting': False, 'chatting' : False,'ability':False}
    if input[pygame.K_LEFT]:
        client_input['left'] = True

    if input[pygame.K_RIGHT]:
        client_input['right'] = True

    if input[pygame.K_LSHIFT]:
        client_input['sprinting'] = True

    if input[pygame.K_UP]:
        client_input['flapping'] = True

    if input[pygame.K_SPACE]:
        client_input['ability'] = True

    return client_input


def main_game_loop(socket: socket.socket): 
    global menu_error
    global game_state
    textBox = TextBox(3, 150, 100, 20, '')
    running = True
    last_client_input = {'flapping': False, 'left': False, 'right': False, 'sprinting': False, 'chatting' : False,'ability':False}
    renderedHealth = render_text('Health: 10',80)
    renderedAmmo = render_text('Ammo: 3', 80)
    while running:
        window.blit(background,(0,0)) # background
        window.blit(ground,(0,600)) # ground
        
        input = pygame.key.get_pressed()
        client_input = get_compacted_input(input)        

        for event in pygame.event.get():
            if event.type == pygame.WINDOWCLOSE:
                pygame.quit()
                exit()

            elif event.type == pygame.KEYDOWN: # if its a keydown button press
                if textBox.active:
                    if event.key == pygame.K_RETURN: # send message, leave chatting
                        commandRan = False
                        if textBox.text.startswith('/'):
                            commandRan = command(textBox.text)
                        if not commandRan:
                            if textBox.text != '':
                                if socket: # if client
                                    msg = encrypt_message(textBox.text,key)
                                    send(socket,f'MSC~{msg}')
                                else: # if server
                                    msg = f'{name}: {textBox.text}'
                                    new_message(msg)
                                    msg = encrypt_message(msg,key)
                                    msg = f'MSS~{msg}'
                                    for client in clients:
                                        send(client,msg)  
                               
                        textBox.text = ''
                        client_input['chatting'] = True
                        textBox.active = False
                    textBox.update(event)


                elif event.key == pygame.K_RETURN and not textBox.active: # enter chatting
                    textBox.active = True
                    client_input['chatting'] = True

                if event.key == pygame.K_ESCAPE and not socket: #exit everything if you're server
                    running = False
                    game_state['menu'] = True
                    if socket == None: # if server
                        msg = f'STT~{json.dumps(game_state)}'.encode()
                        for client in clients:
                            send(client,msg) # send state to clients
                            
                    break
        
        
        for inputName, pressing in client_input.items():
            if pressing:
                if not inputName in game_state['players'][name]['input']:
                    game_state['players'][name]['input'].append(inputName)
            else:
                if inputName in game_state['players'][name]['input']:
                    game_state['players'][name]['input'].remove(inputName)

        if socket == None: # if server
            if random.randint(0,1000) <= 1 and len(game_state['items']) < 10: # random for spawning a weapon
                x = random.randint(30,width-30)
                y = random.randint(100,500)
                game_state['items'].append(('gun',x,y))
                msg = f'STT~{json.dumps(game_state)}'.encode()
                for client in clients:
                    send(client,msg)

        if client_input != last_client_input: # to not spam the server with inputs
            last_client_input = client_input.copy()

            if socket != None: # if client 
                msg = f'INP~{json.dumps(client_input)}'
                send(socket,msg) # send input to server as a client

            else: # if server
                msg = f'STT~{json.dumps(game_state)}'.encode()
                for client in clients:
                    send(client,msg) # send state to clients
        
        last_health = game_state['players'][name]['health']
        last_ammo = game_state['players'][name]['ammo']
        update_state()  
        display_game_state()
        if game_state['players'][name]['chatting']:
            textBox.active = True
        else:
            textBox.active = False
        if textBox.active:
            textBox.draw()

        health = game_state['players'][name]['health']
        ammo = game_state['players'][name]['ammo']
        if health != last_health:
            renderedHealth = render_text(f'Health: {health if health > 0 else 'Dead'} ',80)
        if ammo != last_ammo:
            renderedAmmo = render_text(f'Ammo: {ammo}',80)
        window.blit(renderedHealth,(10,615))
        if ammo > 0:
            window.blit(renderedAmmo,(10,660))
        if game_state['menu']:
            break
        if socket == None: # if server
            players = game_state['players']
            for Player, v in players.items():
                if -5 < players[Player]['health'] <= 0:
                    players[Player]['y'] = 100000 # vanish from map
                    players[Player]['health'] = -1000 # dead
                    new_message(f'{Player} has died.')
                    msg = f'{Player} has died.'
                    msg = 'MSS~' + encrypt_message(msg,key)
                    for client in clients:
                        send(client,msg)
                        send(client,f'STT~{json.dumps(game_state)}'.encode())
        update()
        clock.tick(60)
        if menu_error:
            running = False
            print('quiting to menu because an error has occured')
            break



def display_game_state():
    global colorsDict
    for name, v in game_state['players'].items():
        player = game_state['players'][name]
        x = player['x']
        y = player['y']
        
        if player['right']:
            if player['hurt'] > 0:
                image = bird_hurt
            else:
                image = colorsDict[player['color']][0]
            bird_image = pygame.transform.rotate(image, player['vel']*-6)
            window.blit(bird_image, (x,y))

            if player['item'] != '':
                window.blit(gun,(x+30,y))
            if player['attacking'] > 0:
                image = colorsDict[player['color']][2]
                window.blit(image, (player['x']+ 30,player['y']))
        else:
            if player['hurt'] > 0:
                image = bird_hurt_back
            else:
                image = colorsDict[player['color']][1]
            bird_image = pygame.transform.rotate(image, player['vel'] * 6)
            window.blit(bird_image,(x,y))
            if player['item'] != '':
                window.blit(gunLeft,(x-25,y))

            if player['attacking'] > 0:
                image = colorsDict[player['color']][3]
                window.blit(image, (player['x']-25,player['y']))
        

        print_text(name, x,y+bird_image.get_height()+5,20)

        chat_y = 10

        for image in renderedChatMessages: # print all chat messages
            window.blit(image, (5,chat_y)) 
            chat_y += 13    

        if player['chatting']:
            window.blit(bubble, (x,y-30))
    for item in game_state['items']:
        weapon = item[0]
        x = item[1]
        y = item[2] 
        if weapon == 'gun':
            window.blit(gun,(x,y))
    for bullet in game_state['bullets']:
        right,x,y = bullet[0], bullet[1], bullet[2]
        if (right):
            window.blit(bulletImg,(x,y))
        else:
            window.blit(bulletBack,(x,y))

def check_collision(rect1_pos, rect1_size, rect2_pos, rect2_size):
    x1, y1 = rect1_pos
    w1, h1 = rect1_size
    x2, y2 = rect2_pos
    w2, h2 = rect2_size

    if x1 < x2 + w2 and x1 + w1 > x2 and y1 < y2 + h2 and y1 + h1 > y2:
        return True
    return False

def create_player(name):
    global game_state
    game_state['players'][name] = {# AAA
        'input': [], 'x': 100, 'y': 100, 'health': 10, 'vel': 0, 'right':True,'chatting':False,
        'color':'blue', 'item':'', 'ammo': 0, 'attacking': 0, 'cooldown': 0, 'hurt' : 0, 'knocked': 0
    }            

def reset_players():
    global game_state
    game_state['players'] = {}

def start_game():
    
    game_state['menu'] = False
    global name
    create_player(name)
    players = game_state['players']
    colors = ['blue','red','green','yellow']
    colors_used = []
    for player, v in game_state['players'].items():
        x = random.randint(30,width-30)
        create_player(player) # also resets player
        game_state['players'][player]['x'] = x

        if len(colors_used) >= 4:
            colors_used = []
        color = random.choice(colors)
        while color in colors_used:
            color = random.choice(colors)
        players[player]['color'] = color
        colors_used.append(color)
    game_state['items'] = []    

    
    state_to_send = f'STT~{json.dumps(game_state)}'
    for client in clients:
        send(client,state_to_send)
    main_game_loop(None) # start as server

closeserver_listen = False
def start_server_menu():
    global key
    global menu_error
    global name
    create_player(name)
    key = secrets.token_hex(32)
    buttons = []
    startButton = Button(width-shortButton.get_width()-10,height-shortButton.get_height()-10,"Start",start_game,False)
    buttons.append(startButton)
    closeButton = Button(10,height-shortButton.get_height()-10,"Close Server",None,True)
    buttons.append(closeButton)
    running = True

    server_socket = socket.socket()
    try:
        server_socket.bind(('0.0.0.0', 16969))
        server_socket.listen(8)
    except Exception as e:
        if e.errno == 10048:
            menu_error = "Another socket is already listening on port 16969"
            return
        else:
            print(f"An OSError occurred: {str(e)}")
            return
    
    server_listenThread = threading.Thread(target=server_listen, args=(server_socket,))
    server_listenThread.start()
    print(f'Started thread for listening for clients')
    ip = socket.gethostbyname(socket.gethostname())
    menu_error = ''
    textBox = TextBox(400,600,300,50,'')
    while running:
        window.blit(background, (0,0))
        print_text(f"Opened server on: {ip} port: 16969",width-600,50,40)
        for event in pygame.event.get():
            if event.type == pygame.WINDOWCLOSE:
                pygame.quit()
                exit()
            elif event.type == pygame.MOUSEBUTTONDOWN: #and event.button == 1:
                pos = pygame.mouse.get_pos()
                for button in buttons:
                    if button.is_clicked(pos):
                        if button == closeButton:
                            running = False
                            for client in clients:
                                client.close()
                            break
                        button.function()

            elif event.type == pygame.KEYDOWN: # if its a keydown button press
                if event.key == pygame.K_ESCAPE and len(clients) == 0:
                    running = False
                    break
                elif event.key == pygame.K_RETURN and textBox.text != '': # send message
                    new_message(f'{name}: {textBox.text}')
                    msg = encrypt_message(f'{name}: {textBox.text}',key)
                    msg = f'MSS~{msg}'
                    textBox.text = ''
                    for client in clients:
                        send(client,msg)
                else:
                    textBox.update(event)

        print_text("Connected Players:", width-400, 100, 50)
        print_y = 130
        players = list(game_state['players'])
        for player in players: #print all players connected
            if player != name:
                print_text(player,width-200,print_y,40)
                print_y += 30

        for button in buttons:
            button.draw()
        textBox.draw()
        chat_y = 10
        for image in bigRenderedChatMessages: # print all chat messages
            window.blit(image, (20,chat_y)) 
            chat_y += 35   

        update()
        clock.tick(60)
    clients.clear()
    global closeserver_listen
    closeserver_listen = True
    server_listenThread.join()
    closeserver_listen = False

def client_listening(socket: socket.socket):
    global game_state
    global key
    global menu_error
    while True: # while gamin
        try:
            data = recv(socket)
            parts = data.split('~')
            if parts[0] == 'STT': # game state 
                game_state = json.loads(parts[1])

            elif parts[0] == 'MSS': # server message
                new_message(decrypt_message(parts[1],key))

            
        except Exception as e:
            game_state['menu'] = True 
            if e.errno == 10053: # client aborted connection 
                break
            else:
                print('The server has closed the socket, quitting game, ', end='')
                menu_error = "The server has closed the game"
                break
    print('Thread listening for server has ended')


def update_state():
    global game_state
    players = game_state['players']

    for playerName, v in game_state['players'].items():        
        player = game_state['players'][playerName]
        if player['health'] < 0:
            continue
        input = {'flapping': False, 'left': False, 'right': False, 'sprinting': False, 'chatting' : False,'ability':False}
        for inputName in player['input']:
            input[inputName] =  True


        if player['vel'] < 9: # max velocity check
            player['vel'] += 0.4
        
        if player['y'] < 600-bird_image.get_height()-1 or player['vel'] < 0: # if not below ground OR going up
            player['y'] += int(player['vel'])

        else: # on ground
            player['y'] = 580
            player['vel'] = 0

        if input['chatting']:
            player['chatting'] = not player['chatting']

        to_del = []
        for num in range(len(game_state['items'])):
            item = game_state['items'][num]
            name,x,y = item[0], item[1], item[2]
            if check_collision((player['x'],player['y']),(30,30),(x,y),(30,30)):
                to_del.append(num)
                player['item'] = name
                player['ammo'] += 3
                player['cooldown'] = 2
        to_del.sort(reverse=True) # never deletes out of bound-in-arr items 
        for num in to_del:
            del game_state['items'][num]

        if not player['chatting']:
            if input['flapping'] and player['vel'] > -1 and player['y'] > 0: # if trying to jump and about to reach jump height peak
                player['vel'] = -7 # jump

            if input['sprinting']:
                if input['left']:
                    if player['x'] > 6:
                        player['right'] = False
                        player['x'] -= 6
                if input['right']:
                    if player['x'] < width-bird_image.get_width()-6:
                        player['right'] = True
                        player['x'] += 6
            else:
                if input['left']:
                    if player['x'] > 3:
                        player['right'] = False
                        player['x'] -= 3
                if input['right']:
                    if player['x'] < width-bird_image.get_width()-3:
                        player['right'] = True
                        player['x'] += 3
            
            if input['ability'] and player['cooldown'] <= 0:
                if player['item'] != '':
                    if player['item'] == 'gun':
                        if player['right'] :
                            game_state['bullets'].append( [True,player['x']+50,player['y']] )
                        else:
                            game_state['bullets'].append( [False,player['x']-50,player['y']] )                        
                        player['ammo'] -= 1
                        player['cooldown'] = 10
                    if player['ammo'] <= 0:
                        player['ammo'] = 0
                        player['item'] = ''
                else: 
                    player['attacking'] = 30
                    player['cooldown'] = 60
        
        bullets = game_state['bullets']
        to_del = []

        for num in range(len(bullets)):
            right, x,y = bullets[num][0], bullets[num][1], bullets[num][2]
            if right:
                bullets[num][1] += 20
            else:
                bullets[num][1] -= 20

            if not 0 < bullets[num][1] < width:
                to_del.append(num)
            for playerKey, v in players.items():
                Player = players[playerKey]
                px, py = Player['x'], Player['y']
                if check_collision((px,py),(30,30),(x,y),(30,30)):
                    if not num in to_del:
                        to_del.append(num)
                    if x < Player['x']:
                        Player['knocked'] = 6 # knocked right
                    else:
                        Player['knocked'] = -6 # knocked left

                    Player['health'] -= 1
                    Player['hurt'] = 5
        to_del.sort(reverse=True) # never deletes out of bound-in-arr bullets 
        for num in to_del:
            del bullets[num]

        if player['attacking'] > 0:
            if player['right']:
                x1,y1 = player['x']+30, player['y']
            else:
                x1,y1 = player['x']-30, player['y']
            for otherPlayerKey, v in players.items():
                otherPlayer = players[otherPlayerKey]
                if otherPlayer != player:
                    x2,y2 =otherPlayer['x'],otherPlayer['y']
                    x2Punch = x2
                    if otherPlayer['right']:
                        x2Punch += 30
                    else:
                        x2Punch -= 30
                    
                    if otherPlayer['attacking'] > 0 and check_collision((x1,y1),(30,30),(x2Punch,y2),(30,30)): # if punched another punch
                        for Player in [player,otherPlayer]:
                            if Player['right']:
                                Player['knocked'] = -7 # get knocked left
                            else:
                                Player['knocked'] = 7 # get knocked right
                        player['attacking'] = 0
                        player['cooldown'] = 40
                        otherPlayer['attacking'] = 0
                        otherPlayer['cooldown'] = 40
                    elif check_collision((x1,y1),(30,30),(x2,y2),(30,30)): # 
                        if player['x'] < otherPlayer['x']:
                            otherPlayer['knocked'] = 4 # knocked right
                        else:
                            otherPlayer['knocked'] = -4 # knocked left
                        otherPlayer['health'] -= 1
                        otherPlayer['hurt'] = 5
                        player['attacking'] = 0
                        player['cooldown'] = 40
                        break

        if player['attacking'] > 0:
            player['attacking'] -= 1
        if player['cooldown'] > 0:
            player['cooldown'] -= 1
        if player['hurt'] >0:
            player['hurt'] -= 1
        if player['knocked'] != 0: # if knocked
            if player['knocked'] > 0: # knocked right
                player['knocked'] -= 1
                if player['x'] < width-30:
                    player['x'] += 15
            else:
                player['knocked'] += 1
                if player['x'] > 15:
                    player['x'] -= 15

    
    
def client_thread(conn, player_id):

    clientName = recv(conn) # NAM~<name>
    clientName = clientName.split('~')
    if clientName[0] != 'NAM':
        send(conn,f'ERR~invalid format')
        clients.remove(conn)
        conn.close()
        print(f'Thread {player_id} Listening for {clientName[1]} has ended')
        return
    if not clientName[1] in game_state['players']:
        clientName = clientName[1]
        send(conn,'NAM~OK')
        create_player(clientName)
    else:
        print(f'Error: Player tried to connect with a name that already exists ({clientName[1]})')
        send(conn,'ERR~name exists')
        clients.remove(conn)
        conn.close()
        print(f'Thread {player_id} Listening for {clientName[1]} has ended')
        return
    print(f'{clientName} Connected' )

    clientPublicKey = recv(conn) # RSA~<base64RsaPublicKey>
    clientPublicKey = clientPublicKey.split('~')
    if clientPublicKey[0] != 'RSA':
        send(conn,f'ERR~invalid format')
        clients.remove(conn)
        conn.close()
        return
    clientPublicKey = clientPublicKey[1]
    clientPublicKey = base64.b64decode(clientPublicKey)
    clientPublicKey = RSA.import_key(clientPublicKey)
    encrypter = PKCS1_OAEP.new(clientPublicKey)
    global key
    encrypedKey = encrypter.encrypt(key.encode())
    encrypedKey = base64.b64encode(encrypedKey)
    send(conn,f'RSB~{str(encrypedKey).lstrip('b\'').rstrip('\'')}')

    while True: # while gaming
        try:
            data = recv(conn)

            if not data:
                print(f"Player {player_id} disconnected")
                break  

            parts = data.split('~')

            if parts[0] == 'INP': # input
                input = json.loads(parts[1])   # AAAA    
                for inputName, pressing in input.items():
                    if pressing:
                        if not inputName in game_state['players'][clientName]['input']:
                            game_state['players'][clientName]['input'].append(inputName)
                    else:
                        if inputName in game_state['players'][clientName]['input']:
                            game_state['players'][clientName]['input'].remove(inputName)

                             
                msg = f'STT~{json.dumps(game_state)}'
                for client in clients:
                    send(client,msg)

            elif parts[0] == 'MSC': # message
                message = decrypt_message(parts[1],key)
                msg = f'{clientName}: {message}'
                msg = 'MSS~' + encrypt_message(msg,key)
                for client in clients:
                    send(client,msg)
                new_message(f'{clientName}: {message}')
                game_state['players'][clientName]['chatting'] = False
            




        except Exception as e:
            if e.errno == 10054:
                print(f'{clientName} quit ')
            else:
                print(f'Exception on client thread number {player_id}, name: {clientName}, \nException:{e}\n')
            break  

    del game_state['players'][clientName]
    clients.remove(conn)
    conn.close()
    print(f'Thread {player_id} Listening for {clientName} has ended')


def server_listen(server_socket: socket.socket):
    player_id = 1
    server_socket.settimeout(0.1)
    global closeserver_listen
    while True:
        try:
            conn, address = server_socket.accept() 
            print("Connection from: " + str(address))
            clients.append(conn)

            thread = threading.Thread(target=client_thread, args=(conn, player_id))
            threads.append(thread)
            thread.start()
            print(f'Started a thread for client num {player_id} ')

            player_id += 1
        except socket.timeout:
            if closeserver_listen:
                break
    server_socket.close()
    
def connect_menu():
    global menu_error
    global key
    Socket = socket.socket()
    connectButton = Button(400,400,"Connect",None,False)
    closeButton = Button(10,height-shortButton.get_height()-10,"Close",None,False)
    connectTextBox = TextBox(300,300,100,30,'127.0.0.1')
    buttons = []
    buttons.append(closeButton)
    buttons.append(connectButton)
    running = True
    global game_state
    server_name = ''
    textBox = TextBox(700,600,300,50,'')
    while running:
        window.blit(background,(0,0))
        if server_name:
            print_text(f"Connected to: {server_name} ",width-600,300,50)
            print_text('Waiting for the server to start the game..',width-700,350,50)
            textBox.draw()
        else:
            print_text("Connect To:",100,300,50)
        if menu_error:
            running = False
            break

        for event in pygame.event.get():
            if event.type == pygame.WINDOWCLOSE:
                pygame.quit()
                exit()
            elif event.type == pygame.KEYDOWN: # if its a keydown button press
                if event.key == pygame.K_ESCAPE:
                    running = False
                    break
                elif not server_name: # if still not connected
                    connectTextBox.update(event)
                else:
                    textBox.update(event)
                    if event.key == pygame.K_RETURN and textBox.text != '': # send message
                        msg = encrypt_message(textBox.text,key)
                        send(Socket,f'MSC~{msg}')
                        textBox.text = ''


            elif event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                if connectButton.is_clicked(pos) and not server_name:
                    ip = connectTextBox.text                    
                    if check_ip(ip):
                        try:
                            print_text(f'Trying to connect to {ip}', 200,150,50)
                            update()
                            Socket.connect((ip,16969))
                            send(Socket,f'NAM~{name}')
                            response = recv(Socket).split('~')
                            if response[0] == 'ERR':
                                if response[1] == 'name exists':
                                    menu_error = f'Username \'{name}\' already exists in that game'
                            elif response[0] == 'NAM' and response[1] == 'OK':
                                print_text("Getting key from server...", 200,150,50)
                                update()
                                rsaPublicKey = rsaKey.publickey().export_key()
                                rsaPublicKey = base64.b64encode(rsaPublicKey)
                                send(Socket,f'RSA~{rsaPublicKey.decode()}')

                                encryptedKey = recv(Socket) # RSB~<base64Key>
                                encryptedKey = encryptedKey.split('~')[1]
                                encryptedKey = base64.b64decode(encryptedKey)
                                decypherer = PKCS1_OAEP.new(rsaKey)
                                key = decypherer.decrypt(encryptedKey)
                                
                                print('Connection Successful')
                                server_name = Socket.getpeername()
                                clientListeningThread = threading.Thread(target=client_listening, args= (Socket,))
                                clientListeningThread.start()
                                threads.append(clientListeningThread)
                                print(f'Started a thread for listening to server ')
                        except Exception as e:
                            print(f'Exception during connection to the server:\n\n{e}')
                            if Socket:
                                Socket.close()
                                Socket = socket.socket() # reset socket to prevent 'already tried to connect'
                if closeButton.is_clicked(pos):
                    running = False
                    break
        
        for button in buttons:
            if button == connectButton:
                if not server_name:
                    button.draw()
            else:
                button.draw()
        if not server_name:
            connectTextBox.draw()

        if not game_state['menu']: # if a game has started
            main_game_loop(Socket) # start as a client 

        chat_y = 10
        for image in bigRenderedChatMessages: # print all chat messages
            window.blit(image, (20,chat_y)) 
            chat_y += 35   
        update()
        clock.tick(60)
    
    if Socket: # If its not None
        Socket.close()
    



                
def check_ip(ip):
    nums = ip.split('.')
    if len(nums) != 4:
        return False
    for num in nums:
        if not num.isdigit():
            return False
        i = int(num)
        if i < 0 or i > 255:
            return False
    return True

def main_menu():
    global menu_error
    global name
    global rsaKey
    nameBox = TextBox(450,300,100,60,name)
    running = True
    while running:
        window.blit(background,(0,0)) # background
        print_text('Enter your name:',100,300,60)
        for event in pygame.event.get():
            if event.type == pygame.WINDOWCLOSE:
                pygame.quit()
                exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN and len(nameBox.text) > 0:
                    name = nameBox.text[:16]
                    running = False
                    break
                else:
                    nameBox.update(event)
        nameBox.text = nameBox.text[:16]
        nameBox.draw()
        update()
        if not rsaKey: # calculating rsa key here because the user takes time untill they respond to the menu appearing
            rsaKey = RSA.generate(2048)

    buttons = []
    practiceButton = Button(50,500,"Practice",start_game,True)
    buttons.append(practiceButton)
    startServerButton = Button(450,500,"Start server", start_server_menu,True)
    buttons.append(startServerButton)
    connectButton = Button(850,500,"Connect to server", connect_menu,True)
    buttons.append(connectButton)

    running = True
    while running:
        window.blit(background,(0,0)) # background
        window.blit(logo,(100,20))
        print_text(f'Welcome {name}',450,300,50)
        if menu_error: #if there is an error:
            print_text(menu_error, 600,200,40)
        for event in pygame.event.get():
            if event.type == pygame.WINDOWCLOSE:
                pygame.quit()
                exit()
            elif event.type == pygame.MOUSEBUTTONDOWN: #and event.button == 1:
                pos = pygame.mouse.get_pos()
                for button in buttons:
                    if button.is_clicked(pos):
                        menu_error = ''
                        button.function()
                        reset_players()
                        clear_messages()
                        nameBox.text = name
        for button in buttons:
            button.draw()

        update()
        clock.tick(60)

if __name__ == "__main__":
    main_menu()