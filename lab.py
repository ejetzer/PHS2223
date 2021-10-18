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
import matplotlib as mpl
import matplotlib.pyplot as plt
from pylablib.devices import Thorlabs as Tl
#from ThorlabsPM100 import ThorlabsPM100


# Configuration spéciale de matplotlib pour afficher des graphiques
# Tiré de https://pythonprogramming.net/how-to-embed-matplotlib-graph-tkinter-gui/
mpl.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


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


    @property
    def sommet(self):
        y_max = max(self.puissance)
        x_max = self.position[self.puissance.index(y_max)]
        return x_max, y_max

    @property
    def epsilon(self):
        x_max, y_max = self.sommet
        y_epsilon = y_max / 2
        y_epsilon = trouver_proche(self.puissance, y_epsilon)
        i_1 = self.puissance.index(y_epsilon)
        epsilon = abs(2 * (x_max - self.position[i_1]))
        return y_epsilon, epsilon

    def graphique(self, fig: plt.Figure, ylabel: str = '', xlabel: str = '', title: str = ''):
        ax = fig.gca()
        ax.clear()
        ax.plot(self.position, self.puissance)
        ax.set_ylabel(ylabel)
        ax.set_xlabel(xlabel)
        ax.set_title(title)
        y_epsilon, epsilon = self.epsilon
        x_max, y_max = self.sommet
        ax.annotate(f'$\\epsilon = {epsilon:.2f}$ mm', (x_max, y_epsilon))

        return fig, ax

    def exporter(self, fig: plt.Figure):
        cadre = pd.DataFrame({'Position': self.position, 'Puissance': self.puissance})

        temps = time.ctime().replace(':', '_')
        nom_dossier = pathlib.Path(f"~/Desktop/Résultats {temps}").expanduser()
        nom_dossier.mkdir()
        nom_tableur = nom_dossier / f'Données {temps}.csv'
        nom_image = nom_dossier / f'Données {temps}.png'
        
        cadre.to_csv(nom_tableur)
        fig.savefig(nom_image)

        return nom_tableur, nom_image

    def courriel(self, pièces_jointes: list[str], émmetteur: str):
        contenu = "Voici les données du labo laser:"

        récepteur = 'emile.jetzer@polymtl.ca'

        message = MIMEMultipart()
        message['From'] = émmetteur
        message['To'] = récepteur
        message['Cc'] = émmetteur
        message['Subject'] = 'Données du labo laser'

        message.attach(MIMEText(contenu, 'plain'))
        
        for nom, type_mime in zip(pièces_jointes, (('text', 'csv'), ('image', 'png'))):
            with open(nom, 'rb') as pièce_jointe:
                payload = MIMEBase(*type_mime)
                payload.set_payload(pièce_jointe.read())
                encoders.encode_base64(payload)
                payload.add_header('Content-Disposition', f'attachment; filename={nom.name}')
                message.attach(payload)

        serveur = smtplib.SMTP('smtp.polymtl.ca', 25)
        texte = message.as_string()
        serveur.sendmail(émmetteur, [récepteur, émmetteur], texte)


class DummyPuissancemètre:

    def __init__(self, id_détecteur: tuple[int, int] = None):
        self.__détecteur: usbtmc.Instrument = None #connection au puissance mètre
        self.open()

    def open(self):
        pass

    def close(self):
        pass

    def read(self):
        from random import random
        return random()

class Puissancemètre(DummyPuissancemètre):

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


class DummyMoteur:
    T = 2048 / 6e6  # constante trouver sur https://www.thorlabs.com/Software/Motion%20Control/APT_Communications_Protocol.pdf
    V = 65536
    pas_par_mm = 34304  # Scaling factor en fonction du moteur


    def __init__(self, id_moteur=None):
        self.__moteur = None  # connection du stage
        self.__position = 0
        self.aller(0)
        self.attendre()

    @property
    def position(self):
        return self.__position

    def mesurer(self, détecteur: Puissancemètre, données: Données, dx: float = 6.0):
        nombre_de_pas = dx * self.pas_par_mm #distance a parcourir

        self.aller(0)
        self.attendre()

        données.réinitialiser()
        for i in range(int(nombre_de_pas)):
            self.aller(i)
            x, P = self.position, détecteur.read()
            données.position.append(x)
            données.puissance.append(P)

        self.aller(0)
        self.attendre()

    def aller(self, position_finale: float = 0):
        self.__position = position_finale

    def attendre(self):
        pass

    def close(self):
        pass

class Moteur(DummyMoteur):
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

        self.aller(0)
        self.attendre()

        self.__moteur.move_by(nombre_de_pas) # mouvement

        données.réinitialiser()
        while self.__moteur.is_moving(): # capture de position et puissance
            try:
                x, P =  self.position, détecteur.read()
                données.position.append(x)
                données.puissance.append(P)
            except Exception as ex:
                print(ex)

        self.aller(0)
        self.attendre()

    def aller(self, position_finale: float = 0):
        self.__moteur.setup_velocity(0,250,700005)
        self.__moteur.move_to(position_finale)

    def attendre(self):
        self.__moteur.wait_move()

    def close(self):
        self.__moteur.close()


class LabGui(tk.Frame):

    def __init__(self, maître: tk.Tk, étage_de_translation: Moteur, puissancemètre: Puissancemètre, données: Données, *args, **kargs):
        super().__init__(master=maître, *args, **kargs)

        self.étage_de_translation = étage_de_translation
        self.puissancemètre = puissancemètre
        self.données = données

        self.cadre_formulaire = tk.Frame(self)
        self.bouton_exécuter = tk.Button(self.cadre_formulaire, text="Exécuter", command=lambda: self.exécuter())
        self.cadre_entrée = tk.Frame(self.cadre_formulaire)
        self.variable_courriel = tk.StringVar()
        self.étiquette_courriel = tk.Label(self.cadre_entrée, text='Courriel:')
        self.champ_courriel = tk.Entry(self.cadre_entrée, textvariable=self.variable_courriel)
        
        self.cadre_paramètres = tk.Frame(self)
        self.cadre_xaxis = tk.Frame(self.cadre_paramètres)
        self.variable_xaxis = tk.StringVar()
        self.étiquette_xaxis = tk.Label(self.cadre_xaxis, text='Titre de l\'abscisse:')
        self.champ_xaxis = tk.Entry(self.cadre_xaxis, textvariable=self.variable_xaxis)
        
        self.cadre_yaxis = tk.Frame(self.cadre_paramètres)
        self.variable_yaxis = tk.StringVar()
        self.étiquette_yaxis = tk.Label(self.cadre_yaxis, text='Titre de l\'ordonnée:')
        self.champ_yaxis = tk.Entry(self.cadre_yaxis, textvariable=self.variable_yaxis)
        
        self.cadre_titre = tk.Frame(self.cadre_paramètres)
        self.variable_titre = tk.StringVar()
        self.étiquette_titre = tk.Label(self.cadre_titre, text='Titre du graphique:')
        self.champ_titre = tk.Entry(self.cadre_titre, textvariable=self.variable_titre)
        
        self.figure = plt.Figure(figsize=(10,10))
        self.canevas = FigureCanvasTkAgg(self.figure, self)
        self.outils = NavigationToolbar2Tk(self.canevas, self)

    def pack(self, *args, **kargs):
        self.cadre_formulaire.pack(side=tk.TOP, fill=tk.X)
        self.bouton_exécuter.pack(side=tk.RIGHT)
        self.cadre_entrée.pack(side=tk.LEFT, fill=tk.X)
        self.étiquette_courriel.pack(side=tk.LEFT)
        self.champ_courriel.pack(fill=tk.X)
        
        self.cadre_paramètres.pack(side=tk.TOP, fill=tk.X)
        self.cadre_xaxis.pack(fill=tk.X)
        self.étiquette_titre.pack(side=tk.LEFT)
        self.champ_titre.pack(fill=tk.X)
        self.cadre_yaxis.pack(fill=tk.X)
        self.étiquette_xaxis.pack(side=tk.LEFT)
        self.champ_xaxis.pack(fill=tk.X)
        self.cadre_titre.pack(fill=tk.X)
        self.étiquette_yaxis.pack(side=tk.LEFT)
        self.champ_yaxis.pack(fill=tk.X)
        
        self.outils.update()
        self.canevas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH)

        super().pack(*args, **kargs)

    def exécuter(self):
        self.données.réinitialiser()
        self.étage_de_translation.mesurer(self.puissancemètre, self.données)

        fig, ax = self.données.graphique(self.figure,
                                         self.variable_yaxis.get(),
                                         self.variable_xaxis.get(),
                                         self.variable_titre.get())
        self.canevas.draw()
        
        pièces_jointes = self.données.exporter(self.figure)
        try:
            self.données.courriel(pièces_jointes, self.variable_courriel.get())
        except Exception:
            pass

    def destroy(self):
        self.étage_de_translation.close()
        self.puissancemètre.close()
        super().destroy()

test = False
if test:
    ClasseMoteur, ClassePuissancemètre = DummyMoteur, DummyPuissancemètre
else:
    ClasseMoteur, ClassePuissancemètre = Moteur, Puissancemètre

if __name__ == '__main__':
    fenêtre = tk.Tk()
    fenêtre.title('Labo Laser')
    interface = LabGui(fenêtre, ClasseMoteur(), ClassePuissancemètre(), Données())

    interface.pack()
    fenêtre.mainloop()
