# -*- coding: utf-8 -*-
"""
Created on Tue Aug  3 10:36:48 2021

@author: Émile Jetzer, Vincent Perreault
"""

import time
import smtplib
import pathlib
import tkinter as tk

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Download https://sourceforge.net/projects/libusb-win32/files/latest/download
import usbtmc
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pylablib.devices import Thorlabs as Tl
#from ThorlabsPM100 import ThorlabsPM100


def trouver_proche(liste: list, valeur: float):
    tableau: np.array = np.asarray(liste)
    indice: int = (np.abs(tableau - valeur)).argmin()
    return tableau[indice]


class Données:
    """Classe *mutable* pour faciliter les opérations entre éléments d'interface."""
    
    def __init__(self):
        self.réinitialiser()
    
    def réinitialiser(self):
        self.position: list[float] = []
        self.puissance: list[float] = []
        self.graph = None
    
    @property
    def epsilon(self):
        hepsi = max(self.puissance) / 2 
        va = trouver_proche(self.puissance, hepsi)
        point1 = self.puissance.index(va)
        point2 = self.puissance.index(max(self.puissance))
        epsilon = abs(2 * (self.position[point2] - self.position[point1]))
        return epsilon
    
    def graphique(self):
        self.fig = plt.figure()
        self.ax = plt.plot(self.position, self.puissance)
        plt.ylabel("Puissance (W)")
        plt.xlabel("Position (mm)")
        plt.figtext(0.5, 0.95, '$\\epsilon = {:.2f}$ mm'.format(self.epsilon))
        plt.figtext(0.5, 0.9, '$\\epsilon^2 = {:.2f}$ mm$^2$'.format(self.epsilon**2))

        return self.fig, self.ax
    
    def exporter(self):
        cadre = pd.DataFrame({'Position': self.position, 'Puissance': self.puissance})

        temps = time.ctime().replace(':', '_')
        nom_image = pathlib.Path("~/Desktop/Graph {}.png".format(temps)).expanduser()
        nom_tableur = pathlib.Path("~/Desktop/Data {}.csv".format(temps)).expanduser()

        plt.savefig(nom_image)
        cadre.to_csv(nom_tableur)
        
        return nom_image, nom_tableur
    
    def courriel(self, nom_image: str, nom_tableur: str):
        contenu = "Voici les données du labo laser:"

        émmetteur = 'emile.jetzer@polymtl.ca'
        récepteur = 'emile.jetzer@polymtl.ca'
        
        message = MIMEMultipart()
        message['From'] = émmetteur
        message['To'] = récepteur
        message['Subject'] = 'Labo Laser'
        
        message.attach(MIMEText(contenu, 'plain'))
        
        for nom_fichier, nom_joint, type_joint in ((nom_image, 'graphe.png', ('image', 'png')),
                                                   (nom_tableur, 'tableur.csv', ('text', 'csv'))):
            with open(nom_fichier, 'rb') as pièce_jointe:
                payload = MIMEBase(*type_joint)
                payload.set_payload((pièce_jointe).read())
                encoders.encode_base64(payload)
                payload.add_header('Content-Decomposition', 'attachment', filename=nom_joint)
                message.attach(payload)
        
        serveur = smtplib.SMTP('smtp.polymtl.ca', 25)
        texte = message.as_string()
        serveur.sendmail(émmetteur, récepteur, texte)

class Puissancemètre:
    
    def __init__(self, id_détecteur: tuple[int, int] = None):
        if id_détecteur is None:
            info = str(usbtmc.list_devices()[0]) #liste les appareil connectée
            
            # trouvé les IDs
            posven = info.find('idVendor') 
            id_vendeur = info[posven+25:posven+31] 
            
            pospro = info.find('idProduct')
            id_produit = info[pospro+25:pospro+31]
            
            id_vendeur, id_produit = int(id_vendeur, 16), int(id_produit, 16)
        else:
            id_vendeur, id_produit = id_détecteur
            
        self.__détecteur: usbtmc.Instrument = usbtmc.Instrument(id_vendeur, id_produit) #connection au puissance mètre
        self.open()
    
    def open(self):
        self.__détecteur.open()
    
    def close(self):
        self.__détecteur.close()
    
    def read(self):
        return float(self.__détecteur.ask('READ?'))


class Moteur:
    T = 2048 / 6e6  # constante trouver sur https://www.thorlabs.com/Software/Motion%20Control/APT_Communications_Protocol.pdf
    V = 65536
    pas_par_mm = 34304  # Scaling factor en fonction du moteur
    
    
    def __init__(self, id_moteur=None):
        if id_moteur is None:
            id_moteur = Tl.list_kinesis_devices()[0][0]  # list l'ID du stage
        
        self.__moteur = Tl.KinesisMotor(id_moteur)  # connection du stage
        self.aller(0)
        self.attendre()
    
    @property
    def position(self):
        return float(self.__moteur.get_position() / self.pas_par_mm)

    def mesurer(self, détecteur: Puissancemètre, données: Données, dx: float = 6.0):
        nombre_de_pas = dx * self.pas_par_mm #distance a parcourir
        self.__moteur.setup_velocity(0, 250, 100005)
        self.__moteur.move_by(nombre_de_pas) # mouvement

        données.réinitialiser()
        while self.__moteur.is_moving(): # capture de position et puissance
            try:
                x, P =  self.position, détecteur.read()
                données.position.append(x)
                données.puissance.append(P)
            except Exception as ex:
                print(ex)

        données.graphique()
    
    def aller(self, position_finale: float = 0):
        self.__moteur.setup_velocity(0,250,700005)
        self.__moteur.move_to(position_finale)
    
    def attendre(self):
        self.__moteur.wait_move()
    
    def close(self):
        self.__moteur.close()
            


def lab():
    try:
        étage_de_translation = Moteur()
        puissancemètre = Puissancemètre()
        données = Données()
        étage_de_translation.mesurer(puissancemètre, données)
        fig, ax = données.graphique()
        noms = données.exporter()
        #données.courriel(*noms)
        fig.show()
    finally:    
        étage_de_translation.close()
        puissancemètre.close()
    

if __name__ == '__main__':
    fenêtre = tk.Tk()
    fenêtre.title('Labo Laser')

    bouton_exécuter = tk.Button(fenêtre, text="Executer", fg='black', bg='green',
                                command=lab, height=10, width=25)

    bouton_exécuter.pack()
    fenêtre.mainloop()
