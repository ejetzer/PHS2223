# -*- coding: utf-8 -*-
"""
Created on Tue Aug  3 10:36:48 2021

@author: Admin
"""
# Download https://sourceforge.net/projects/libusb-win32/files/latest/download
import numpy as np
import time
from pylablib.devices import Thorlabs as Tl
import usbtmc
from ThorlabsPM100 import ThorlabsPM100
import matplotlib.pyplot as plt
import decimal
import pandas as pd
import tkinter as tk
from tkinter import *
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


class Données:
    
    def __init__(self):
        self.xdata = []
        self.ydata = []
        self.data = None
        self.graph = None
        

def inimotor():
    '''
    

    Returns
    -------
    stage : TYPE
        Initiation du Stage du moteur de façon automatique ou manuel et retourne l'objet représentant celui-ci'

    '''
    manautobool=False 
    while not manautobool: # Choix manuel/auto
        manauto = 'a'
        if manauto in ['m','a']: #VÉrification du choix
            manautobool = True
        else:
            print("Choix invalide")
    if manauto in ['m']: # Choix manuel
        idbool = False
        while not idbool: # numero de série stage
            idnum = input("entrer le numéro de série du module:  " )
            if int(idnum) & len(idnum)==8: # Vérification du choix
                idbool = True 
            else:
                print("Le ID est composé de 8 chiffres")
        try:
            stage = Tl.KinesisMotor(idnum) #connection au stage
            return stage
        except Exception as ex:
            print("Tentative de connection échouée")
            print("Revérifier le numéro de série")
            print(ex)
    if manauto in ['a']: # Choix auto
        idnum = Tl.list_kinesis_devices()[0][0] #list l'ID du stage
        try:
            stage = Tl.KinesisMotor(idnum) # connection du stage
            return stage
        except Exception as ex:
            print("Tentative de connection échouée")
            print("Si le problème persiste utiliser la connection manuel")
            print(ex)
        
def find_nearest(array, value):
    '''
    

    Parameters
    ----------
    array : TYPE
        Liste des puissances
    value : TYPE
        La valeur rechercher

    Returns
    -------
    TYPE
        la valeur dans la liste puissance la plus près de la valeur recherchée

    '''
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return array[idx]

def movemotor(stage, inst, données):
    '''
    
    

    Parameters
    ----------
    stage : TYPE
        objet représentant le stage
    inst : TYPE
        objet représentant le puissancemètre

    Returns
    -------
    None.

    '''
    T=2048/(6*10**6) #constante trouver sur https://www.thorlabs.com/Software/Motion%20Control/APT_Communications_Protocol.pdf
    V=65536
    normcustbool= False
    while not normcustbool: # choix reglage base (pour le labo) ou auto
        normcust= 'b'
        if normcust in ['b','c']: # vérification
            normcustbool = True
        else:
            print('Choix invalide')
    if normcust in ['b']: # Choix base
        enccnt = 34304 # Scaling factor en fonction du moteur
        dist = 5 ## déplacement en mm voulu
        movem=dist*enccnt #distance a parcourire
        stage.setup_velocity(0,250,100005)
        stage.move_by(movem) # mouvement
        i = 0
        position = []
        puissance = []
        while stage.is_moving(): # capture de position et puissance
            try:
                nouv_pos = stage.get_position()/enccnt
                nouv_pui = inst.ask("READ?")
                position.append(float(nouv_pos))
                puissance.append(float(nouv_pui))
                i = i+1
            except Exception as ex:
                print(ex)
        # Recherche epsilon
        #print('puissance = ' + repr(puissance))
        hepsi = max(puissance)/2 
        va = find_nearest(puissance, hepsi)
        point1 = puissance.index(va)
        point2 = puissance.index(max(puissance))
        epsilon = abs(2*(position[point2]-position[point1]))
        données.xdata = position
        données.ydata = puissance
        # Graphique
        graph = plt.plot(position,puissance)
        plt.ylabel("Puissance (W)")
        plt.xlabel("Position (mm)")
        plt.figtext(0.5,0.95,'$\\epsilon = {}$'.format(epsilon))
        plt.figtext(0.5,0.9,'$\\epsilon^2 = {}$'.format(epsilon**2))
        
        plt.show()
        
        
    if normcust in ['c']: # Choix custom
        enccntbool = False
        enccntvelbool = False
        enccntaccbool = False
        velbool = False
        accbool = False
        print("Voir: https://www.thorlabs.com/Software/Motion%20Control/APT_Communications_Protocol.pdf p.39 pour les facteurs de conversion")
        while not enccntbool: # facteur position
            try:
                enccnt = float(input('Entrer le facteur de conversion de déplacement du moteur:  '))
                enccntbool = True
            except ValueError: # vérification
                print("Valeur invalide")
        while not enccntvelbool: # Facteur Vitesse
            try:
                enccntvel = float(input('Entrer le facteur de conversion de vitesse du moteur:  '))
                enccntvel = enccntvel*T*V 
                enccntvelbool = True
            except ValueError: # vérification
                print("Valeur invalide")
        while not enccntaccbool: # facteur accélération 
            try: 
                enccntacc = float(input("Entrer le facteur de conversion d'accelerationdu moteur:  "))
                enccntacc = enccntacc*T**2*V
                enccntaccbool = True
            except ValueError: # vérification
                print('Valeur invalide')
        while not accbool: # Accélération
            try:
                acc = float(input("Entrer l'accélération(mm/s^2):  "))
                accbool = True
            except ValueError: # vérification
                print("Valeur invalide")
        while not velbool: #vitesse max
            try:
                vel = float(input("Entrer la vitesse (mm/s):  "))
                velbool = True
            except ValueError: # vérification
                print("Valeur invalide")
        stage.setup_velocity(0, acc*enccntacc ,vel*enccntvel) # réglages de vitesse
        continubool = False
        while not continubool:
            movechoixbool = False
            while not movechoixbool: # Choix de mode de mouvement
                movejogchoix = input("Choisir le mode voulu: Jog(j), Move_by(mb), Move_to(mt). Pour plus d'infomration sur les choix (h):  ").lower()
                if movejogchoix in ['j','mb','mt']: #vérification
                    movechoixbool = True
                elif movejogchoix in ['h']: # help
                    print("Jog: Mouvement continu du plateau pendant une durée de temps déterminé")
                    print("Move_by: Déplacement du plateau sur une distance donnée")
                    print("Move_to: Déplacement du plateau à la position donnée")
                else:
                    print('Entrée invalide')
            if movejogchoix in ['mb']: # Choix move by
                movembool = False
                movenumbool = False
                movedelaybool = False
                while not movembool: # dépalcement réglages
                    try:
                        movem = float(input("Entrer le déplacement(mm):  "))
                        movembool = True
                    except ValueError: # vérification
                        print("Valeur invalide")
                while not movenumbool: # nombre de répétition
                    try:
                        movenum = int(input("Nombre de répédition(0 ne fera que l'action une seul fois):  "))
                        movenumbool = True
                        if movenum != 0:
                            while not movedelaybool: # délai de répétition
                                try: 
                                    movedelay = float(input("Entrer le délai entre chaque déplacement(s):  "))
                                    movedelaybool = True
                                except ValueError: # vérification
                                    print("Valeur invalide")
                        elif movenum == 0: # sans répétition
                            movedelay = 0
                    except ValueError:  # vérification
                        print("Valeur invalide")
                for x in range(movenum+1): #déplacement   
                    stage.move_by(movem*enccnt)
                    stage.wait_move()
                    time.sleep(movedelay)
            if movejogchoix in ['j']: # Choix jog
                jogbool = False
                jognumbool = False
                jogdelaybool = False
                while not jogbool: # déplacement réglage
                    try:
                        temps=float(input("Entrer le temps de déplacement(s):  "))
                        jogbool = True
                    except ValueError:  # vérification
                        print("Valeur invalide")
                while not jognumbool: # nombre de répétition
                    try:
                        jognum = int(input("Entrer le nombre de répédition(0 ne fera que l'action une seul fois):  "))
                        jognumbool = True
                        if jognum != 0 :
                            while not jogdelaybool: # délai entre les répétitions
                                try:
                                    jogdelai = float(input("Entrer le temps entre les répéditons(s):  "))
                                    jogdelaybool = True
                                except ValueError: # vérification
                                    print("Valeur invalide")
                        elif jognum == 0: # sans répétition
                            jogdelai = 0
                    except ValueError:
                        print("Valeur invalide")
                for x in range(jognum+1): # déplacement
                    stage.jog("+")
                    time.sleep(temps)
                    stage.stop()
                    time.sleep(jogdelai)
            if movejogchoix in ['mt']: # choix mouve to
                movmtobool = False
                while not  movmtobool: # réglage déplacement
                    try:
                        movmto = float(input("Entrer la position(mm):  "))
                        movmtobool = True
                    except ValueError: # vérification
                        print("Valeur invalide")
                stage.move_to(movmto*enccnt) #déplacement
                stage.wait_move()
            continuchoix = input("Faire une autre action(a) ou Quitter(q):  ") # refaire une action
            if continuchoix in ['q','a']: # vérification
                if continuchoix in ['q']: #fermeture
                    continubool = True
            else:
                print("Entrée invalide")

def setupmeter():
    '''
    

    Returns
    -------
    inst : TYPE
        objet représentant l'instrument (le puissancemètre)'

    '''
    boolsetup = False
    while not boolsetup: # choix manuel/auto
        setupchoix = 'a'
        if setupchoix in ['m','a']: # vérification
            boolsetup = True
        else:
            print("Choix invalide") 
    if setupchoix in ['a']: # choix automatique
        try:
            info = str(usbtmc.list_devices()[0]) #liste les appareil connectée
            # trouvé les IDs
            posven = info.find('idVendor') 
            idven = info[posven+25:posven+31] 
            pospro = info.find('idProduct')
            idpro = info[pospro+25:pospro+31]
            inst = usbtmc.Instrument(int(idven,16),int(idpro,16)) #connection au puissance mètre
            return inst
        except Exception as e: # vérification
            print("Tentative de connection échouée")
            print("Si le problème persiste utiliser la connection manuel")
            print('Détails:')
            print(e)
    if setupchoix in ['m']: #choix manuel
        # entrer de ID (0x1234) ou (4567)
        idven = input("Entrer le numéro d'indentification du vendeur:  ") 
        idpro = input("Enter le numéro d'indentification du produit:  ")
        try:
            inst = usbtmc.Instrument(int(idven,16),int(idpro,16)) #connection au puissance mètre
            return inst
        except Exception as ex: # vérification
            print("Tentative de connection échouée")
            print("Revérifier les numéros d'indentifications")
            print(ex)
            


def lab(données):
    print('Intialisation du moteur...')
    stage = inimotor() # initiation du moteur
    print('Moteur initialisé.')
    print('Position de départ: {}'.format(stage.get_position()))
    stage.setup_velocity(0,250,700005) # réinitialiser la vitesse
    stage.move_to(0) # retour au point 0
    stage.wait_move()
    print('Connexion au puissance-mètre...')
    inst = setupmeter() # initiation puissancemètre
    inst.open()
    print('Puissance-mètre connecté.')
    try:
        movemotor(stage, inst, données) #mouvement
        print(stage.get_position())
    except Exception as ex:
        txterror = Text(window, height = 2, width = 30)
        txterror.pack()
        txterror.insert(tk.END, "Erreur. Asseyer de nouveau (cela peut prendre quelques essais)")
        window.after(5000, txterror.destroy)
        print(ex)
    finally:
        inst.close()    
        stage.close()
   
     
def export(données, window):
    print('Export...')
    print('Conversion en dataframe...')
    exp = pd.DataFrame(list(zip(données.xdata, données.ydata)), columns=['Position','Puissance'])
    print('Transpose...')
    #exp = exp.T
    temps = time.ctime()
    temps = temps.replace(':', '-')
    namepng = "/Users/PHS2223/Desktop/Graph {}.png".format(temps)
    nameexl = "/Users/PHS2223/Desktop/data_output {}.csv".format(temps)
    print('savefig')
    plt.savefig(namepng)
    print('figsaved')
    exp.to_csv(nameexl)
    print('xlsaved')
    mail_content = "Ceci est les données du lab d'optique"


    sender_address = 'emile.jetzer@polymtl.ca'
    receiver_address = 'emile.jetzer@polymtl.ca'
    #sender_pass = 'xxxxxxxx'
    
    message = MIMEMultipart()
    message['From'] = sender_address
    message['To'] = receiver_address
    message['Subject'] = 'Labo Optique'
    
    message.attach(MIMEText(mail_content, 'plain'))
    attach_file_name = namepng
    attach_file = open(attach_file_name, 'rb') # Open the file as binary mode
    
    attach_file2_name = nameexl
    attach_file2 = open(attach_file2_name, 'rb') # Open the file as binary mode
    
    payload = MIMEBase('image', 'png')
    payload.set_payload((attach_file).read())
    encoders.encode_base64(payload)
    payload.add_header('Content-Decomposition', 'attachment', filename='Graph.png')
    message.attach(payload)
    
    payload = MIMEBase('application', 'excel')
    payload.set_payload((attach_file2).read())
    encoders.encode_base64(payload)
    payload.add_header('Content-Decomposition', 'attachment', filename='Data.xlsx')
    message.attach(payload)
    
    session = smtplib.SMTP('smtp.polymtl.ca',25)
    text = message.as_string()
    session.sendmail(sender_address, receiver_address, text)
    
    texto = Text(window, height = 2, width = 30)
    texto.insert(tk.END, "Données enregistrées")
    texto.pack()
    window.after(3000, texto.destroy)
    
        
'''
inst = setupmeter()
inst.open()
print(inst.ask("READ?"))
print(inst.ask("READ?"))
inst.close() 
'''
données = Données()
window=Tk()
btnexe=Button(window, text="Éxecuter", fg='black')
btnexe.place(x=50, y=50)
btnexe.config(height = 10, width = 25, bg='Green', command = lambda: lab(données))
window.title('Lab Laser')
window.geometry("500x300+10+20")
btnexp=Button(window, text="Éxporter", fg='black' , command = lambda: export(données, window))
btnexp.place(x=250, y=50)
btnexp.config(height = 10, width = 25, )
window.mainloop()


'''
stage=Tl.KinesisMotor("83863195")
stage.home()
stage.wait_for_home()
stage.jog("+")
time.sleep(1.)
stage.stop()
stage.move_to(10)
stage.wait_move()
print(stage.get_position())
stage.close()
'''
