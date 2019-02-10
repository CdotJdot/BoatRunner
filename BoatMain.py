import tkinter
import math
import time
from random import randrange
import tkinter.ttk
from PIL import ImageTk, Image

'''
General notes:
Not much new in the way of general notes since I haven't researched a bunch of stuff like I did last time. Just throwing
the updated code your way. No worries if the progress on your end is minimal (or even nonexistent), any pace is fine. 
Perhaps we should start using Git though so that the updated code can be provided without intrusion. I made an account 
on GitHub and I watched an intro vid to using Git but it just seemed so cumbersome and tedious. Perhaps PyCharm has 
features that can make it not shitty, I'll have to look into that soon. My next two goals are to optimize/ clean the 
code and to implement a moving camera on a larger map.
    

Changelog (big changes only, not going to go into as much detail this time):
- I ripped off the Kirby Air Ride powerup system. Powerups work as you would expect them too, although picking up too 
    many of them can cause issues with boat control. I'll have to fine tune them more and add limiters or something.
- I gave the NPCs better AI. There are now three types of them, each has a unique attack style and clear vulnerability 
    periods. They scale with time to increase the difficulty. Only the one that doesn't shoot does melee collision dmg.
- Added collision damage for projectiles. Some enemies have projectiles as well. All collision still only applies to 
    the back point of a boat. The current approach to collision is far too slow and computation heavy. I will have to 
    do some research and determine a better way.
- Player projectile now fires automatically at max charge.
'''


def collision(b, a):
    # b and a are bounding boxes x1, y1, x2, y2 [(top left)(bottom right)]
    # https://silentmatt.com/rectangle-intersection/
    if not a or not b:
        return False
    if a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]:
        return True
    return False


def distance_function(pt1, pt2):
    dx = pt1[0] - pt2[0]
    dy = pt1[1] - pt2[1]
    distance = math.sqrt(dy ** 2 + dx ** 2)
    return distance


def check_dir(back_point, front_point):
    # INPUT: pnt, pnt
    # Computes angle between two points on a grid w/ respect to point 1
    # RETURN: float radians
    horizontal = [front_point[0], back_point[1]]
    adjacent = distance_function(back_point, horizontal)
    hypotenuse = distance_function(back_point, front_point)

    if adjacent == 0 or adjacent == hypotenuse:
        if front_point[0] > back_point[0]:
            base_angle = 0
        else:
            base_angle = math.radians(90)
    else:
        if (front_point[0] - back_point[0]) * (front_point[1] - back_point[1]) < 0:
            base_angle = math.asin(adjacent / hypotenuse)
        else:
            base_angle = math.acos(adjacent / hypotenuse)

    if front_point[0] < back_point[0] and front_point[1] >= back_point[1]:
        return base_angle + math.radians(90)
    elif front_point[0] <= back_point[0] and front_point[1] < back_point[1]:
        return base_angle + math.radians(180)
    elif front_point[0] > back_point[0] and front_point[1] < back_point[1]:
        return base_angle + math.radians(270)
    else:
        return base_angle


def hidden_space():
    return [-100.0, -100.0]


def oob_check(map_length, position):
    if position[0] < 0 or position[1] < 0:
        return True
    elif position[0] > (1.4 * map_length) or position[1] > map_length:
        return True
    else:
        return False


class BoatStartupFrame:
    # Has a reset, single player, exit button
    def __init__(self, master, framesize):
        self.master = master
        self.framesize = framesize
        self.new_game = None
        self.background_image = ImageTk.PhotoImage(Image.open("Wiki-background.png"))
        self.start_image = ImageTk.PhotoImage(Image.open("start_button.png"))
        self.game_frame = tkinter.Frame(self.master, width=framesize*1.4, height=framesize, background='dark blue', pady=10, padx=10)
        self.background_label = tkinter.Label(self.game_frame, image=self.background_image, height=framesize*.97, width=framesize*1.4*.98)
        self.game_frame.grid_propagate(0)
        self.background_label.grid(row=0, column=0)
        self.start_button = tkinter.Button(self.game_frame, text='boats in space', pady=10, padx=50, command=self.button_pressed, image=self.start_image)
        self.start_button.grid(row=0, column=0)
        self.game_frame.grid(row=0, column=0)
        self.master.mainloop()

    def button_pressed(self):
        self.start_button.grid_forget()
        self.background_label.grid_forget()
        self.game_frame.grid_propagate(1)
        self.new_game = BoatGameUI(self, 60, self.framesize)

    def remove_game(self):
        self.game_frame.grid_propagate(1)
        self.background_label.grid(row=0, column=0)
        self.start_button.grid(row=0, column=0)
        del self.new_game
        self.new_game = None


class Boat:

    # Constructor. Takes canvas size and boat length
    def __init__(self, map_length, master, weapon):
        self.master = master
        self.weapon = weapon
        self.score = 0
        self.canvas_tag = 'pboat'
        self.canvas_body_tag = 'pboatbody'
        self.first_pass = True
        self.direction_mem = 0
        self.life = 1
        self.health_max = 100.0
        self.health_current = self.health_max
        self.defense = 1.0
        self.invincible = False
        self.i_frames = 30.0
        self.i_end = 0.0
        self.length = 70
        self.vel = 0  # Units of
        self.vel_limits = [5, 0]  # Units of
        self.accel = [0.2, -0.01]  # Units of
        self.turn_rate = [0.05, 0.10]
        self.time_step = 1.0
        self.charge = 0.0
        self.max_charge = 0.6
        self.boost_remainder = 0.0
        self.boost_duration = 40.0    # Number of frames boost lasts for
        self.boost_magnitude = 1.0
        self.max_boost_mag = 1.2
        self.boost_bonus = 0.1  # Additional percent of max boost added to the executed boost (scales with mag)
        self.charge_status = 0
        self.key_stats = [self.boost_duration, self.boost_bonus, self.max_charge, self.defense, self.health_max,
                          self.weapon.vel_max, self.weapon.vel_min, self.vel_limits[0], self.turn_rate[0], self.turn_rate[1]]
        self.upgrade_rate = 0.03    # Each pickup improves that stat by x%
        self.upgrade_increments = [x * self.upgrade_rate for x in self.key_stats]
        self.front_point = [map_length / 2, map_length / 2]     # Would probs be better to base front point off of back point (currently the opposite is happening)
        self.back_point = [(map_length / 2) - self.length, map_length / 2]  # Also I'll make spawn location into random
        self.body = master.create_line(self.back_point, self.front_point, arrow=tkinter.LAST, arrowshape='20 80 20', fill="green", tags=[self.canvas_tag, self.canvas_body_tag])
        self.back_image = ImageTk.PhotoImage(Image.open("back_track.png"))
        self.front_image = ImageTk.PhotoImage(Image.open("front_track.png"))
        self.front = master.create_image(self.back_point, image=self.back_image, tag=self.canvas_tag)
        self.back = master.create_image(self.front_point, image=self.front_image, tag=self.canvas_tag)
        self.alive = True

    def boost(self, charge_time):
        self.charge = charge_time
        if self.charge > self.max_charge / 2:
            self.boost_remainder = self.boost_duration
            if self.charge > self.max_charge:
                self.boost_magnitude = self.max_boost_mag + (self.boost_bonus * self.max_boost_mag)
            else:
                self.boost_magnitude = ((self.max_boost_mag - 1) * (self.charge / self.max_charge)) + 1

    def despawn(self):
        self.master.itemconfigure(self.canvas_tag, state='hidden')

    # To be called each frame. Uses utility functions below to update boat position.
    def move(self, mouse_cursor):
        if not self.alive:
            return
        if self.front_point != mouse_cursor:
            self.front_point = self.turning(mouse_cursor, self.back_point, self.front_point, 0)
        self.vel = self.vel_update(self.time_step)
        split_vel = self.vel_split()
        self.vel_move(split_vel, self.time_step)
        self.master.coords(self.body, self.back_point[0], self.back_point[1], self.front_point[0], self.front_point[1])
        self.master.coords(self.front, self.front_point)
        self.master.coords(self.back, self.back_point)

    def turning(self, goal_point, back_pt, front_pt, offset):
        current_dir = check_dir(back_pt, front_pt)
        goal_dir = check_dir(back_pt, goal_point)
        goal_dir += math.radians(offset)
        if math.degrees(goal_dir) > 360:
            goal_dir -= math.radians(360)
        if abs(current_dir - goal_dir) < self.turn_rate[self.charge_status]\
                or math.radians(360) - abs(current_dir - goal_dir) < self.turn_rate[self.charge_status]:
            new_dir = goal_dir
        else:
            if abs(current_dir - goal_dir) <= math.radians(180):
                if current_dir > goal_dir:
                    new_dir = current_dir - self.turn_rate[self.charge_status]    # CW Turn
                else:
                    new_dir = current_dir + self.turn_rate[self.charge_status]    # CCW Turn
            else:
                if current_dir > goal_dir:
                    new_dir = current_dir + self.turn_rate[self.charge_status]    # CCW Turn
                else:
                    new_dir = current_dir - self.turn_rate[self.charge_status]    # CW Turn
        length = distance_function(self.back_point, self.front_point)
        x_new = self.back_point[0] + length * math.cos(new_dir)
        y_new = self.back_point[1] + length * math.sin(new_dir)
        move_point = [x_new, y_new]
        return move_point

    def vel_update(self, dt):
        self.vel += self.accel[self.charge_status] * (self.boost_magnitude ** 1.5) * dt
        if self.vel > self.vel_limits[0] * self.boost_magnitude:
            self.vel = self.vel_limits[0] * self.boost_magnitude
        elif self.vel < self.vel_limits[1]:
            self.vel = self.vel_limits[1]
        if self.boost_remainder != 0:
            self.boost_remainder -= 1
            if self.boost_remainder <= 0:
                self.boost_remainder = 0.0
                self.boost_magnitude = 1.0
        return self.vel

    def vel_split(self):
        if self.charge_status == 1:
            if self.first_pass:
                current_dir = check_dir(self.back_point, self.front_point)
                self.direction_mem = current_dir
                self.first_pass = False
            else:
                current_dir = self.direction_mem
        else:
            self.first_pass = True
            current_dir = check_dir(self.back_point, self.front_point)
        x_vel = self.vel * math.cos(current_dir)
        y_vel = self.vel * math.sin(current_dir)
        return [x_vel, y_vel]

    def vel_move(self, vel, dt):
        self.back_point[0] += vel[0] * dt
        self.back_point[1] += vel[1] * dt
        self.front_point[0] += vel[0] * dt
        self.front_point[1] += vel[1] * dt

    def take_dmg(self, dmg_magnitude):
        if time.time() >= self.i_end:
            self.invincible = False
        if not self.invincible:
            self.health_current -= self.defense * dmg_magnitude
            self.invincible = True
            self.i_end = time.time() + (self.i_frames / BoatGameUI.fps)
            if self.health_current <= 0:
                self.life -= 1
                if self.life <= 0:
                    self.alive = False


class NPCBoat(Boat):

    def __init__(self, map_length, master, weapon):
        Boat.__init__(self, map_length, master, weapon)
        self.front_point = hidden_space()   # Probs should rework boat classes to take spawn_point input
        self.back_point = hidden_space()
        self.canvas_tag = 'eboat'
        master.delete(self.body, self.front, self.back)     # Need to rework boat classes to take spawn_point input imo
        self.body = master.create_line(self.back_point, self.front_point, arrow=tkinter.LAST, arrowshape='20 80 20', fill="purple", tag=self.canvas_tag)
        self.front = master.create_image(self.back_point, image=self.back_image, tag=self.canvas_tag)
        self.back = master.create_image(self.front_point, image=self.front_image, tag=self.canvas_tag)
        self.type_options = ['zipper', 'sitter', 'poker']
        self.enemy_type = randrange(0, len(self.type_options))
        self.type_choice = self.type_options[self.enemy_type]
        self.type_label = ''
        self.unique_atrbs = []  # Attributes that are unique to a particular type of enemy
        self.ai_state = 'spawn'
        self.time_marker = 0.0
        self.shooter = False
        self.i_frames = 0.0

    def apply_type(self, diff_mult):
        if self.type_choice == 'zipper':
            self.type_zipper(diff_mult)
        elif self.type_choice == 'sitter':
            self.type_sitter(diff_mult)
        elif self.type_choice == 'poker':
            self.type_poker(diff_mult)

    def type_zipper(self, diff_mult):
        self.type_label = self.type_options[0]
        self.shooter = True
        self.vel_limits[0] *= 1.2 * diff_mult
        self.turn_rate[0] *= 0.5
        self.turn_rate[1] *= 1.2
        self.accel[1] *= 5.5
        self.health_max *= 0.5
        self.health_current = self.health_max
        self.weapon.damage *= 0.5
        self.length = randrange(60, 81)
        self.unique_atrbs.append([self.length * 7.0, self.length * 10.0])    # Distance range that enemy tries to maintain with player
        self.unique_atrbs.append(0.0)       # Stores offset value for turning
        self.unique_atrbs.append(180)       # Time enemy spends maintaining a range until shooting
        self.unique_atrbs.append(90 * (2.0 - diff_mult))        # Time enemy spends charging before shooting
        self.unique_atrbs.append(30)        # Time enemy spends aiming boost after shooting

    def zipper_move(self, player_pos, enemy_back, enemy_front, offset):
        if not self.alive:
            return
        if self.front_point != player_pos:
            self.front_point = self.turning(player_pos, enemy_back, enemy_front, offset)
        self.vel = self.vel_update(self.time_step)
        split_vel = self.vel_split()
        self.vel_move(split_vel, self.time_step)
        self.master.coords(self.body, self.back_point[0], self.back_point[1], self.front_point[0], self.front_point[1])
        self.master.coords(self.front, self.front_point)
        self.master.coords(self.back, self.back_point)

    def zipper_ai(self, target):
        if self.ai_state == 'spawn':
            self.ai_state = 'maintain_range'
            self.time_marker = time.time()  # Might be pointless
        if self.ai_state == 'maintain_range':
            if distance_function(self.back_point, target.front_point) > self.unique_atrbs[0][0]:
                self.unique_atrbs[1] = 0
            elif distance_function(self.back_point, target.front_point) < self.unique_atrbs[0][1]:
                self.unique_atrbs[1] = 180
            else:
                self.unique_atrbs[1] = 90
            self.zipper_move(target.front_point, self.back_point, self.front_point, self.unique_atrbs[1])
            if time.time() >= self.time_marker + (self.unique_atrbs[2] / BoatGameUI.fps):
                self.ai_state = 'shooting'
                self.charge_status = 1
                self.time_marker = time.time()
        elif self.ai_state == 'shooting':
            self.zipper_move(target.front_point, self.back_point, self.front_point, 0)
            if time.time() >= self.time_marker + (self.unique_atrbs[3] / BoatGameUI.fps):
                self.weapon.fire(self.back_point, self.front_point, self.weapon.vel_max)
                self.ai_state = 'boost_aim'
                self.time_marker = time.time()
        elif self.ai_state == 'boost_aim':
            self.zipper_move(target.front_point, self.back_point, self.front_point, 90)
            if time.time() >= self.time_marker + (self.unique_atrbs[4] / BoatGameUI.fps):
                self.boost(self.unique_atrbs[3] + self.unique_atrbs[4])
                self.charge_status = 0
                self.ai_state = 'maintain_range'

    def type_sitter(self, diff_mult):
        self.type_label = self.type_options[1]
        self.shooter = True
        self.vel_limits[0] = 0
        self.turn_rate[1] *= 1.2
        self.health_max *= 1.2 * diff_mult
        self.weapon.vel_min *= diff_mult
        self.health_current = self.health_max
        self.weapon.damage *= 0.5
        self.length = randrange(1, 21)
        self.unique_atrbs.append(90)    # Number of frames after spawn until enemy starts firing
        self.unique_atrbs.append(0)     # Keeps track of shots fired until enemy needs to reload
        self.unique_atrbs.append(15)    # Number of frames enemy waits between individual shots
        self.unique_atrbs.append(360)   # Number of frames enemy waits as it reloads

    def sitter_move(self, player_pos, enemy_back, enemy_front, offset):
        if not self.alive:
            return
        self.charge_status = 1
        if self.front_point != player_pos:
            self.front_point = self.turning(player_pos, enemy_back, enemy_front, offset)
        self.master.coords(self.body, self.back_point[0], self.back_point[1], self.front_point[0], self.front_point[1])
        self.master.coords(self.front, self.front_point)
        self.master.coords(self.back, self.back_point)

    def sitter_ai(self, target):
        if self.ai_state == 'spawn':
            self.sitter_move(target.front_point, self.back_point, self.front_point, 0)
            if time.time() >= self.time_marker + (self.unique_atrbs[0] / BoatGameUI.fps):
                self.ai_state = 'shooting'
        elif self.ai_state == 'shooting':
            self.sitter_move(target.front_point, self.back_point, self.front_point, 0)
            self.weapon.fire(self.back_point, self.front_point, 0.0)
            self.unique_atrbs[1] += 1
            if self.unique_atrbs[1] == 3:
                self.ai_state = 'reloading'
                self.unique_atrbs[1] = 0
            else:
                self.ai_state = 'shot_delay'
            self.time_marker = time.time()
        elif self.ai_state == 'shot_delay':
            self.sitter_move(target.front_point, self.back_point, self.front_point, 0)
            if time.time() >= self.time_marker + (self.unique_atrbs[2] / BoatGameUI.fps):
                self.ai_state = 'shooting'
        elif self.ai_state == 'reloading':
            self.sitter_move(target.front_point, self.back_point, self.front_point, 0)
            if time.time() >= self.time_marker + (self.unique_atrbs[3] / BoatGameUI.fps):
                self.ai_state = 'shooting'

    def type_poker(self, diff_mult):
        self.type_label = self.type_options[2]
        self.shooter = False
        self.vel_limits[0] *= 0.4
        self.turn_rate[0] *= (2 / 3)
        self.accel[1] *= 4.5
        self.max_boost_mag *= 4.5 * diff_mult
        self.boost_duration *= 2.8
        self.health_max *= 2.0
        self.health_current = self.health_max
        self.length = randrange(150, 181)
        self.unique_atrbs.append(self.length * 6.5)   # Distance from player that enemy needs to be before charging
        self.unique_atrbs.append(150 * (2.0 - diff_mult))   # Number of frames enemy charges for
        self.unique_atrbs.append(300)   # Number of frames enemy moves past player for (direction locked)
        self.unique_atrbs.append(50)    # Damage dealt by ramming into player

    def poker_move(self, player_pos, enemy_back, enemy_front, offset, turn_or_not):
        if not self.alive:
            return
        if turn_or_not:
            if self.front_point != player_pos:
                self.front_point = self.turning(player_pos, enemy_back, enemy_front, offset)
        self.vel = self.vel_update(self.time_step)
        split_vel = self.vel_split()
        self.vel_move(split_vel, self.time_step)
        self.master.coords(self.body, self.back_point[0], self.back_point[1], self.front_point[0], self.front_point[1])
        self.master.coords(self.front, self.front_point)
        self.master.coords(self.back, self.back_point)

    def poker_ai(self, target):
        if self.ai_state == 'spawn':
            if distance_function(self.front_point, target.back_point) > self.unique_atrbs[0]:
                self.ai_state = 'charge'
                self.time_marker = time.time()
            else:
                self.ai_state = 'reposition'
        elif oob_check(1000, self.back_point):      # Ideally avoid using map length as a raw number
            self.charge_status = 0
            self.poker_move(target.front_point, self.back_point, self.front_point, 0, True)
            if not oob_check(1000, self.back_point):    # Ideally avoid using map length as a raw number
                self.ai_state = 'charge'
                self.time_marker = time.time()
        if self.ai_state == 'charge':
            self.charge_status = 1
            self.poker_move(target.front_point, self.back_point, self.front_point, 0, True)
            if time.time() >= self.time_marker + (self.unique_atrbs[1] / BoatGameUI.fps):
                self.ai_state = 'boost'
                self.boost(self.max_charge)
                self.charge_status = 0
                self.time_marker = time.time()
        elif self.ai_state == 'boost':
            self.poker_move(target.front_point, self.back_point, self.front_point, 0, False)
            if time.time() >= self.time_marker + (self.unique_atrbs[2] / BoatGameUI.fps):
                self.ai_state = 'reposition'
        elif self.ai_state == 'reposition':
            self.poker_move(target.back_point, self.back_point, self.front_point, 180, True)
            if distance_function(self.front_point, target.back_point) > self.unique_atrbs[0]:
                self.ai_state = 'charge'
                self.time_marker = time.time()

    def despawn(self):      # Check if this is being used, delete if not
        self.master.itemconfigure(self.canvas_tag, state='hidden')
        #self.master.delete(self.body, self.front, self.back)
        self.alive = True


class NPCFactory:

    # When called, takes a root (Canvas)
    # Creates set amount of NPC boats on this canvas, indexes them each

    def __init__(self, map_length, master):
        self.master = master
        self.screen_size = map_length
        self.enemy_list = []
        self.enemy_shots_dict = {}
        self.size = 0   # Size does not seem to be used for anything?
        self.spawn_rate = 500   # Meaning an enemy will spawn once every x frames
        self.diff_multiplier = 1.0
        self.diff_increase = 0.01   # Magnitude of difficulty increase
        self.diff_rate = 500     # Number of frames until difficulty increases

    def spawn_enemy(self):
        enemy_weapon = StarProjectile(self.master, 1)
        enemy_boat = NPCBoat(self.screen_size, self.master, enemy_weapon)
        enemy_boat.apply_type(self.diff_multiplier)
        enemy_boat.time_marker = time.time()
        if enemy_boat.shooter:
            self.enemy_shots_dict[enemy_boat] = enemy_weapon
        else:
            self.enemy_shots_dict[enemy_boat] = None
        enemy_boat.front_point = [randrange(1, self.screen_size * 1.4), randrange(1, self.screen_size)]
        enemy_boat.back_point = [enemy_boat.front_point[0] - enemy_boat.length, enemy_boat.front_point[1]]
        self.enemy_list.append(enemy_boat)
        self.size += 1      # Is this doing something?

    def despawn_enemy(self, enemy):
        enemy.alive = False
        self.master.delete(enemy.body, enemy.front, enemy.back)
        del self.enemy_shots_dict[enemy]
        self.enemy_list.remove(enemy)

    def process_enemies(self, map_build, player):   # Kinda messy...
        for enemy in self.enemy_list:
            if collision(map_build.bbox(player.front), map_build.bbox(enemy.back)):
                self.despawn_enemy(enemy)   # Ramming an enemy is an instakill currently
                player.score += 1
                continue    # This approach to collision will eventually slow the game down significantly...
            player.weapon.hit_detect(map_build, enemy)
            if enemy.health_current <= 0:
                self.despawn_enemy(enemy)
                player.score += 1
                continue
            if enemy.shooter:
                enemy.weapon.hit_detect(map_build, player)
            if enemy.type_label == 'zipper':
                enemy.zipper_ai(player)
                self.enemy_shots_dict[enemy].move_proj()
            elif enemy.type_label == 'sitter':
                enemy.sitter_ai(player)
                self.enemy_shots_dict[enemy].move_proj()
            elif enemy.type_label == 'poker':
                if collision(map_build.bbox(enemy.front), map_build.bbox(player.back)):
                    player.take_dmg(enemy.unique_atrbs[3])
                enemy.poker_ai(player)


class Powerup:

    def __init__(self, map_length, master):
        self.screen_size = map_length
        self.master = master
        self.active = False
        self.key_stats = []
        self.location = [randrange(1, self.screen_size * 1.4), randrange(1, self.screen_size)]
        self.img_open = 'TBD'
        self.img_convert = 'TBD'
        self.visual = 'TBD'
        self.type_options = ['boost', 'charge', 'defense', 'health', 'offense', 'top_speed', 'turn']
        self.current_type = self.type_options[randrange(0, len(self.type_options))]

    def create_visual(self):
        if self.current_type == 'boost':
            self.img_open = Image.open("boost.png")
        elif self.current_type == 'charge':
            self.img_open = Image.open("charge.png")
        elif self.current_type == 'defense':
            self.img_open = Image.open("defense.png")
        elif self.current_type == 'health':
            self.img_open = Image.open("health.png")
        elif self.current_type == 'offense':
            self.img_open = Image.open("offense.png")
        elif self.current_type == 'top_speed':
            self.img_open = Image.open("top speed.png")
        elif self.current_type == 'turn':
            self.img_open = Image.open("turn.png")
        self.img_convert = ImageTk.PhotoImage(self.img_open)
        self.visual = self.master.create_image(self.location, image=self.img_convert, tag='powerup')

    def apply_effect(self, boat):
        if self.current_type == 'boost':
            boat.boost_duration += boat.upgrade_increments[0]
            boat.boost_bonus += boat.upgrade_increments[1]
        elif self.current_type == 'charge':
            boat.max_charge -= boat.upgrade_increments[2]
        elif self.current_type == 'defense':
            boat.defense -= boat.upgrade_increments[3]
        elif self.current_type == 'health':
            boat.health_max += boat.upgrade_increments[4]
            boat.health_current += boat.upgrade_increments[4]
            if boat.health_current < boat.health_max:
                boat.health_current += 0.1 * boat.health_max    # Gives additional healing if not at max health
                if boat.health_current > boat.health_max:
                    boat.health_current = boat.health_max
        elif self.current_type == 'offense':
            boat.weapon.vel_max += boat.upgrade_increments[5]
            boat.weapon.vel_min += boat.upgrade_increments[6]
        elif self.current_type == 'top_speed':
            boat.vel_limits[0] += boat.upgrade_increments[7]
        elif self.current_type == 'turn':
            boat.turn_rate[0] += boat.upgrade_increments[8]
            boat.turn_rate[1] += boat.upgrade_increments[9]


class PowerupFactory:

    def __init__(self, map_length, master):
        self.master = master
        self.screen_size = map_length
        self.powerup_list = []
        self.spawn_rate = 415   # Meaning a powerup will spawn once every x frames

    def spawn(self):
        new_powerup = Powerup(self.screen_size, self.master)
        self.powerup_list.append(new_powerup)
        new_powerup.create_visual()

    def despawn(self, powerup):
        powerup.master.delete(powerup.visual)
        self.powerup_list.remove(powerup)

    def pickup_powerup(self, map_build, player):
        for powerup in self.powerup_list:
            if collision(map_build.bbox(powerup.visual), map_build.bbox(player.front)) \
                    or collision(map_build.bbox(powerup.visual), map_build.bbox(player.back)):
                powerup.apply_effect(player)
                self.despawn(powerup)


class StarProjectile:   # probably should be minimum delay between each shot even if all are available

    def __init__(self, master, star_choice):
        self.master = master
        self.star_choice = star_choice
        self.star_mario = Image.open("star.png")
        self.star_j = Image.open("j.png")
        self.star_choices = [self.star_mario, self.star_j]
        self.star_image = ImageTk.PhotoImage(self.star_choices[star_choice])
        self.identity_max = 3     # up to 3 projectiles can exist at once
        self.identity_current = 0
        self.active_check = [False, False, False]
        self.positions_proj = [hidden_space(), hidden_space(), hidden_space()]
        self.vels = [hidden_space(), hidden_space(), hidden_space()]
        self.damage = 50.0
        self.vel_min = 6.5
        self.vel_max = 10.5
        self.charge = 0.0
        self.max_charge = 0.45
        self.dur_max = 2.2
        self.dur_remain = [float(0), float(0), float(0)]
        self.star1 = master.create_image(self.positions_proj[0], image=self.star_image, state='hidden')
        self.star2 = master.create_image(self.positions_proj[1], image=self.star_image, state='hidden')
        self.star3 = master.create_image(self.positions_proj[2], image=self.star_image, state='hidden')
        self.star_imgs = [self.star1, self.star2, self.star3]   # probs should use some sort of append system with function input number of projectiles

    def img_move(self, identity):
        self.master.coords(self.star_imgs[identity], self.positions_proj[identity])

    def spawn(self, identity):
        self.active_check[identity] = True
        self.master.itemconfigure(self.star_imgs[identity], state='normal')
        self.img_move(identity)

    def despawn(self, identity):
        self.active_check[identity] = False
        self.positions_proj[identity] = hidden_space()
        self.vels[identity] = [0.0, 0.0]
        self.master.itemconfigure(self.star_imgs[identity], state='hidden')

    def change_identity(self):
        if self.identity_current == self.identity_max - 1:
            self.identity_current = 0
        else:
            self.identity_current += 1

    def determine_vel_proj(self, charge_time):
        if charge_time > self.max_charge:
            charge = self.max_charge
        else:
            charge = charge_time
        vel = (charge / self.max_charge) * self.vel_max
        if vel < self.vel_min:
            vel = self.vel_min
        return vel

    def vel_split_proj(self, back_pt, front_pt, identity, charge_time):
        current_dir = check_dir(back_pt, front_pt)
        vel = self.determine_vel_proj(charge_time)
        x_vel = vel * math.cos(current_dir)
        y_vel = vel * math.sin(current_dir)
        self.vels[identity] = [x_vel, y_vel]

    def fire(self, back_pt, front_pt, charge_time):
        if self.dur_remain[self.identity_current] == 0:
            x_pos = front_pt[0]     # Bugs NPCs if I don't split into x and y here...
            y_pos = front_pt[1]
            self.positions_proj[self.identity_current] = [x_pos, y_pos]  # WHY DOES THIS CHANGE THE VALUE OF FRONT_POINT IF NOT SPLIT ?!!?!?!!?!?!
            self.spawn(self.identity_current)
            self.vel_split_proj(back_pt, front_pt, self.identity_current, charge_time)
            self.img_move(self.identity_current)
            self.dur_remain[self.identity_current] = self.dur_max
            self.change_identity()

    def hit_detect(self, map_build, getting_shot):
        for projectile in range(len(self.star_imgs)):
            if self.dur_remain[projectile] > 0 and self.active_check[projectile]:
                if collision(map_build.bbox(self.star_imgs[projectile]), map_build.bbox(getting_shot.back)):
                    getting_shot.take_dmg(self.damage)
                    self.despawn(projectile)
                    if getting_shot.health_current <= 0:
                        return

    def vel_move_proj(self, identity, dt):
        self.positions_proj[identity][0] += self.vels[identity][0] * dt
        self.positions_proj[identity][1] += self.vels[identity][1] * dt

    def move_proj(self):
        for star in range(self.identity_max):
            if self.dur_remain[star] < 1 / BoatGameUI.fps:
                self.dur_remain[star] = 0.0
                if self.active_check[star]:
                    self.despawn(star)
            else:
                if self.active_check[star]:
                    self.vel_move_proj(star, 1)
                    self.img_move(star)
                self.dur_remain[star] -= (1 / BoatGameUI.fps)


class BoatGameUI:

    # Set up properties
    fps = float(60)
    previous_frame_time = 0.0
    frame_count = 0
    time_step = 1
    charge_timer = 0.0
    wep_charge = 0.0
    marked_charge = 0.0
    firing = False
    game_over = False
    tkinter_frame_id = 0

    def __init__(self, ui_frame, fps, map_length):
        self.ui_frame = ui_frame
        self.root = ui_frame.game_frame
        self.fps = fps
        self.map_length = map_length
        self.map_build = tkinter.Canvas(self.root, width=(map_length*1.4), height=map_length, bg='black', borderwidth='0')
        self.player_shots = StarProjectile(self.map_build, 0)
        self.playerBoat = Boat(map_length, self.map_build, self.player_shots)
        self.stats = self.compute_stats()
        self.readout = tkinter.Label(self.root, height=1, width=90, bg='blue', foreground="yellow", relief='sunken', text=self.stats)
        self.map_build.bind('<Button-1>', self.start_charge)
        self.map_build.bind('<ButtonRelease-1>', self.end_charge)
        self.map_build.bind('<Button-3>', self.start_fire)
        self.map_build.bind('<ButtonRelease-3> ', self.end_fire)
        self.map_build.focus_set()
        self.enemies = NPCFactory(self.map_length, self.map_build)
        self.powerups = PowerupFactory(self.map_length, self.map_build)
        self.map_build.grid(row=0, column=0)
        self.readout.grid(row=0, column=0, sticky='n', pady=20)
        self.game_loop()
        self.root.mainloop()

    def start_charge(self, event):
        Boat.boost_remainder = 0.0
        Boat.boost_magnitude = 1.0
        self.charge_timer = time.time()
        self.playerBoat.charge_status = 1

    def end_charge(self, event):
        charge_time = time.time() - self.charge_timer
        self.playerBoat.charge_status = 0
        self.playerBoat.boost(charge_time)

    def start_fire(self, event):
        #if event.keycode == 32:
        self.firing = True
        self.wep_charge = time.time()
        self.marked_charge = self.wep_charge + self.playerBoat.weapon.max_charge

    def end_fire(self, event):
        #if event.keycode == 32:
        if self.firing:
            charge_time = time.time() - self.wep_charge
            self.playerBoat.weapon.fire(self.playerBoat.back_point, self.playerBoat.front_point, charge_time)
            self.firing = False

    def fire_check(self):
        if self.firing:
            if self.marked_charge - time.time() < 1 / self.fps:
                self.playerBoat.weapon.fire(self.playerBoat.back_point, self.playerBoat.front_point, self.playerBoat.weapon.max_charge)
                self.firing = False

    # Helper function to print player stats using text box
    def compute_stats(self):
        stat_string = "\t  Health :" + "{0:.2f}".format(self.playerBoat.health_current)
        stat_string += "\t Velocity :" + "{0:.2f}".format(self.playerBoat.vel)
        stat_string += "\t Accel :" + "{0:.2f}".format(self.playerBoat.accel[self.playerBoat.charge_status])
        #stat_string += "\t Charge :" + "{0:.2f}".format(self.charge_bar.bar["value"])
        stat_string += "\t Boost Remaining :" + "{0:.2f}".format(self.playerBoat.boost_remainder)
        stat_string += "\t Score :" + "{0:.2f}".format(self.playerBoat.score)
        return stat_string

    def get_mouse(self):
        abs_coord_x = self.root.winfo_pointerx() - self.root.winfo_rootx()
        abs_coord_y = self.root.winfo_pointery() - self.root.winfo_rooty()
        mouse_cursor = [abs_coord_x, abs_coord_y]
        return mouse_cursor

    def draw_stats(self):
        self.stats = self.compute_stats()
        self.readout.config(text=self.stats)

    def draw_npc_boat(self):
        self.enemies.process_enemies(self.map_build, self.playerBoat)
        if not self.playerBoat.alive:
            self.end_game()
        if self.frame_count % round(self.enemies.spawn_rate) == 0:
            self.enemies.spawn_rate *= (1.0 - (self.enemies.diff_increase / 2))
            self.enemies.spawn_enemy()
        if self.frame_count % self.enemies.diff_rate == 0:
            self.enemies.diff_multiplier += self.enemies.diff_increase

    def draw_powerup(self):
        self.powerups.pickup_powerup(self.map_build, self.playerBoat)
        if self.frame_count % self.powerups.spawn_rate == 0:
            self.powerups.spawn()

    def draw_boat(self):
        self.playerBoat.move(self.get_mouse())

    def draw_projectiles(self):
        self.player_shots.move_proj()
        self.fire_check()

    def draw_frame(self):
        #print("drawing")
        print("loop time :", time.time() - self.previous_frame_time)
        self.frame_count += 1
        self.draw_boat()
        self.draw_projectiles()
        self.draw_npc_boat()
        self.draw_powerup()
        self.draw_stats()
        self.map_build.update()
        self.previous_frame_time = time.time()

    def animate(self):
        self.draw_frame()
        self.previous_frame_time = time.time()
        if not self.game_over:
            self.tkinter_frame_id = self.map_build.after(8, self.animate)

    def game_loop(self):
        self.frame_count += self.time_step
        self.animate()

    def end_game(self):
        self.ui_frame.remove_game()
        self.map_build.grid_forget()
        self.readout.grid_forget()
        self.game_over = True


def game_run():

    root = tkinter.Tk()
    root.title("Boat Game")
    BoatStartupFrame(root, 1000)


def main():
    game_run()


main()

# TODO
'''
1. I think it would be better if the projectile could be shot from both spacebar and right click (without cancelling 
    itself or creating other issues)
2. Scroll area -> Make it so driving keep camera center and moves around the "map" (If we are going the City Trial + 
    .io game route, this is absolutely necessary, for duel arena, I currently prefer static camera)
3. Further improve AI
4. read http://ezide.com/games/writing-games.html for networking <- (Yes networking, very good.)
5. Cleaning up and optimizing the code
6. Everything needs to magically scale somehow regardless of window resizing... (try going to any .io game and messing 
    around with your browser window size)
7. Fine tune powerups and add limiters
8. Rework projectile object
9. Unify time system better (frames vs time.time() markers)
10. Redo and optimize the collision system
'''
