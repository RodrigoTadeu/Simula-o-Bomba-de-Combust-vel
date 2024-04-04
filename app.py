from flask import Flask, render_template, request, send_file, jsonify
import I2C_LCD_driver
import serial
from threading import Thread
import time
from pad4pi import rpi_gpio
import RPi.GPIO as GPIO
import datetime
import requests
import json
import subprocess
import math

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

GPIO.setup(19, GPIO.OUT)
GPIO.output(19,1)
GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

mylcd0 = I2C_LCD_driver.lcd(0x27)

#PAD
vetor = ["0","0","0","0","0","0"]
vetorLitros = ["0","0","0","0","0","0"]
vetorLitrosPad=[]
vetorGasolinaPad=[]
vetorDataHora=[]

#WEB
vetor3 = ["0","0","0","0","0","0","0"]
vetor4=[]

botoes_travados=[]
litros=0.0

enderecoVerificarAssinatura="http://simulacao.cermob.com.br:45180/restapi/fuel/verify"

precoLitroGasolinha = 5.29
precoLitroGasolinhaStr="5.29"
reaisStr=""
litrosStr=""
abast=""
newMlStr=""
contagemReaisStr=""

bombaGasolinaEmUso=False
web=False
pad1=False
flag1=False

modoR="Reais: "
modoL="Litros: "

tamanho_dado=[0X17]
combustivelGasolina=[0X01]

idEquipamentoGasolina="13279-01"
vetIdEquipamentoGasolina=[0X84, 0X4F, 0X00, 0X01]

KEYPAD = [
        ["F1","F2","#","*"],
        ["1","2","3","CIMA"],
        ["4","5","6","BAIXO"],
        ["7","8","9","ESC"],
        ["ESQUERDA","0","DIREITA","ENTER"]
]

ROW_PINS = [23, 24, 25, 8, 7]
COL_PINS = [21, 20, 16, 12]

factory = rpi_gpio.KeypadFactory()

keypad = factory.create_keypad(keypad=KEYPAD, row_pins=ROW_PINS, col_pins=COL_PINS)
mylcd0.lcd_display_string("R$/L:",4,0)
mylcd0.lcd_display_string(str(precoLitroGasolinha),4,16)

def desligarUsb():
    comando = "sudo uhubctl -l 1-1 -p 2 -a 0"
    subprocess.run(comando, shell=True)

desligarUsb()

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('app.html')

@app.route('/notaFiscal')
def notaFiscal():
    return send_file("/home/pi/Projetos/bmc-supply-simulation/simulationPython/appWeb/static/nota_abastecimento_gasolina.txt", as_attachment=True)

@app.route('/gasolina', methods= ['GET','POST'])
def gasolina():
     global bombaGasolinaEmUso
     if bombaGasolinaEmUso==True:
         return render_template('app.html', flag=bombaGasolinaEmUso)
     return render_template('escolherModo.html')

@app.route('/valor', methods= ['GET','POST'])
def valor():
     escolherPagar(1,modoR)
     return render_template('gasolina.html')

@app.route('/abastecerGasolina', methods= ['GET','POST'])
def abastecerGasolina():
     global bombaGasolinaEmUso,web,veiculoAbastecidoGasolina,f2,reais
     f2=False
     reais=True
     if bombaGasolinaEmUso==True:
         return render_template('app.html', flag=bombaGasolinaEmUso)
     web=True
     bombaGasolinaEmUso=True
     veiculoAbastecidoGasolina =False
     ContadorWeb(litros,startAbastecimento(mylcd0),mylcd0,precoLitroGasolinha)
     mylcd0.lcd_display_string("0.00",2,16)
     while not veiculoAbastecidoGasolina:
         time.sleep(0.1)
     return render_template('abastecimentoGasolina.html', mensagem='Veículo Abastecido')

@app.route('/litros', methods= ['GET','POST'])
def litros():
     escolherPagar(2,modoL)
     return render_template('escolherModoLitro.html')

@app.route('/abastecerLitros', methods= ['GET','POST'])
def abastecerLitros():
     global bombaGasolinaEmUso,web,veiculoAbastecidoGasolina,f2,reais
     f2=False
     reais=False
     if bombaGasolinaEmUso==True:
         return render_template('app.html', flag=bombaGasolinaEmUso)
     web=True
     bombaGasolinaEmUso=True
     veiculoAbastecidoGasolina =False
     ContadorWeb(litros,startAbastecimentoLitros(mylcd0),mylcd0,precoLitroGasolinha)
     mylcd0.lcd_display_string("0.00",1,16)
     while not veiculoAbastecidoGasolina:
         time.sleep(0.1)
     return render_template('abastecimentoGasolina.html', mensagem='Veículo Abastecido')

@app.route('/baixarNotaFiscalGasolina')
def baixarNotaFiscalGasolina():
    return send_file("/home/pi/Projetos/bmc-supply-simulation/simulationPython/appWeb/static/nota_abastecimento_gasolina.txt", as_attachment=True)

@app.route('/returnHome', methods= ['GET','POST'])
def returnHome():
     return render_template('app.html')

@app.route('/atualizacaoBomba/01', methods= ['GET','POST'])
def atualizacaoBomba():
     if abast=="Abastecendo":
         data = {'valorAtual': contagemReaisStr, 'valorFinal':reaisStr,'litrosAtual': newMlStr,'litrosFinal':litrosStr,'valorPorLitro': precoLitroGasolinhaStr, 'status': abast}
     else:
         data = {'valorAtual': reaisStr,'valorFinal':reaisStr,'litrosAtual': litrosStr,'litrosFinal':litrosStr,'valorPorLitro': precoLitroGasolinhaStr, 'status': abast}
     print(data)
     return jsonify(data)


######## FUNCTIONS QUE OS DOIS USAM ##########

def valorAbastecimento(vetor2):
    strReais = "".join(vetor2)
    reais = float(strReais)/100
    return reais

def somaLitrosGasolina(vetorGasolina, litros,mylcd, litrosTotal):
    global veiculoAbastecidoGasolina,bombaGasolinaEmUso
    bombaGasolinaEmUso=True
    tipo="320101001(Gasolina)"
    precoLitro="{:.2f}".format(float(precoLitroGasolinha))
    print('ASSINANDO DADOS BOMBA DE GASOLINA')
    serialData(valorAbastecimento(vetorGasolina),combustivelGasolina, litrosTotalGasolina,precoLitroGasolinha,vetIdEquipamentoGasolina)

    if status!=None:
        with open("/home/pi/Projetos/bmc-supply-simulation/simulationPython/appWeb/static/nota_abastecimento_gasolina.txt","w") as arquivo:
            arquivo.write("Dados de abastecimento\nTipo: "+ tipo+"\nVolume: " +litrosStr+"\nValor total: "+reaisStr+"\nValor Litro: "+precoLitro+"\nDataHora: "+str(datetime.datetime(ano, mes, dia, hora, minuto, segundo))+"\nID equipamento: "+idEquipamentoGasolina+"\nIntegridade dos dados: "+status+"\nDado: "+dado+"\nAssinatura: "+assinatura+"\nChave publica: " +chavePublica)

    mylcd0.lcd_clear()
    if status!=None:
        mylcd0.lcd_display_string(status,1,0)
    else:
        mylcd0.lcd_display_string("Falha na Conexao",1,0)

    time.sleep(5)

    mylcd0.lcd_clear()
    mylcd0.lcd_display_string("R$/L:",4,0)
    mylcd0.lcd_display_string(str(precoLitroGasolinha),4,16)
    mylcd0.lcd_display_string("R$:",1, 0)
    mylcd0.lcd_display_string("Litros:",2, 0)

    atualizacaoLcd(valorAbastecimento(vetorGasolina),reaisStr,litrosTotalGasolina,litrosStr)

    veiculoAbastecidoGasolina=True
    bombaGasolinaEmUso=False

def Contador(litros, reais, mylcd, precoLitro):
  global litrosTotalGasolina,litrosTotalEtanol,litrosTotalAssinar,litrosTotalAssinarStr
  if mylcd==mylcd0:
    litrosTotal1 = reais / precoLitro
    litrosTotalGasolina = round(litrosTotal1, 2)
    litrosTotalAssinar = round(litrosTotal1/100, 2)
    litrosTotalAssinarStr ="{:.2f}".format(litrosTotalAssinar)
    if f2==False:
        mylcd.lcd_display_string("0.00",2,16)
    if f2==True:
        mylcd.lcd_display_string("0.00",1,16)

def ContadorWeb(litros, reais, mylcd, precoLitro):
  global litrosTotalGasolina,litrosTotalEtanol,litrosTotalAssinar
  if mylcd==mylcd0:
    litrosTotal1 = reais / precoLitro
    litrosTotalGasolina = round(litrosTotal1, 2)
    litrosTotalAssinar = round(litrosTotal1/100, 2)

def dividir8bits(parte_inteira):
    binario_completo = bin(parte_inteira)[2:].zfill((parte_inteira.bit_length() + 7) // 8 * 8)
    grupos_de_8_bits = [binario_completo[i:i + 8] for i in range(0, len(binario_completo), 8)]
    total_hexadecimal = ['0x' + hex(int(grupo, 2))[2:].zfill(2) for grupo in grupos_de_8_bits]
    return total_hexadecimal

def dividir3bytes(hex_total):
    tamanho_desejado = 3
    vetor_resultante = ['0'] * tamanho_desejado
    i = tamanho_desejado - len(hex_total)
    for valor in hex_total:
        vetor_resultante[i] = valor
        i += 1
    print(vetor_resultante)
    return vetor_resultante

def dividirHex(valor):
    parte_inteira = int(valor)
    parte_decimal = valor % 1
    parte_decimal = int(round(round(parte_decimal,2)*100,1))
    print(valor)
    print("Parte inteira:", parte_inteira)
    print("Parte decimal:", parte_decimal)

    hex_total = dividir8bits(parte_inteira)+dividir8bits(parte_decimal)
    hex_ints = [int(hex_string, 16) for hex_string in dividir3bytes(hex_total)]
    return hex_ints

def dataHora():
    global ano,mes,dia,hora,minuto,segundo
    ano = datetime.datetime.now().year
    mes = datetime.datetime.now().month
    dia = datetime.datetime.now().day
    hora = datetime.datetime.now().hour
    minuto = datetime.datetime.now().minute
    segundo = datetime.datetime.now().second

    ano_hex=dividir8bits(ano)
    vetorDataHora = [int(x, 16) for x in ano_hex]
    vetorDataHora.append(mes)
    vetorDataHora.append(dia)
    vetorDataHora.append(hora)
    vetorDataHora.append(minuto)
    vetorDataHora.append(segundo)
    return vetorDataHora

def editarLcd():
    mylcd0.lcd_clear()
    mylcd0.lcd_display_string("R$/L:",4,0)
    mylcd0.lcd_display_string(str(precoLitroGasolinha),4,16)
    mylcd0.lcd_display_string("R$:",1, 0)
    mylcd0.lcd_display_string("Litros:",2, 0)
    mylcd0.lcd_display_string("0.00",1,16)
    mylcd0.lcd_display_string("0.00",2,16)

def atualizacaoLcd(reais,reaisStr,litros,litrosStr):
    if reais<10:
        mylcd0.lcd_display_string(str(reaisStr),1,16)
    elif reais<100:
        mylcd0.lcd_display_string(str(reaisStr),1,15)
    elif reais<1000:
        mylcd0.lcd_display_string(str(reaisStr),1,14)
    else:
        mylcd0.lcd_display_string(str(reaisStr),1,13)

    if litros<10:
        mylcd0.lcd_display_string(str(litrosStr),2,16)
    elif litros<100:
        mylcd0.lcd_display_string(str(litrosStr),2,15)
    elif litros<1000:
        mylcd0.lcd_display_string(str(litrosStr),2,14)
    else:
        mylcd0.lcd_display_string(str(litrosStr),2,13)

def lrc(self):
    _lrc = 0x00
    for i in self:
        _lrc ^= i
    return _lrc

def desligarUsb():
    comando = "sudo uhubctl -l 1-1 -p 2 -a 0"
    subprocess.run(comando, shell=True)

def ligarUsb():
    comando = "sudo uhubctl -l 1-1 -p 2 -a 1"
    subprocess.run(comando, shell=True)

def serialData(reais, combustivel, litros,precoPorLitro,vetIdEquipamento):
    global dado, assinatura, chavePublica, status,tentativas,flag1, newMl,contagemReais, web,pad1,litrosStr,reaisStr,abast,contagemReaisStr,newMlStr
    dado=assinatura=chavePublica=status=""
    flag1=False
    tentativas=0
    newMl=0
    contagemReais=0
    newMlStr="0.00"
    contagemReaisStr="0.00"
    abast="Abastecendo"
    reaisStr="{:.2f}".format(reais)
    litrosStr="{:.2f}".format(litros)

    vetPronto = tamanho_dado + combustivel + dividirHex(reais) + dividirHex(litros) + dividirHex(precoPorLitro) + vetIdEquipamento + dataHora()
    vetPronto.append(lrc(vetPronto))
    vetPronto_semLrc = combustivel + dividirHex(reais) + dividirHex(litros) + dividirHex(precoPorLitro) + vetIdEquipamento + dataHora()

    editarLcd()

    ser=serial.Serial('/dev/ttyS0',115200,bytesize=serial.EIGHTBITS,parity=serial.PARITY_NONE,stopbits=serial.STOPBITS_ONE, timeout=3)
    buf=[hex(numero) for numero in vetPronto]
    buf1 =[hex(numero) for numero in vetPronto_semLrc]
    ser.write(bytearray(int(num, 16) for num in buf))
    dado = ''.join(format(int(i, 16), '02x') for i in buf1)
    print('sended: ', buf)
    ser.flush()
    GPIO.output(19,0)

    while flag1 == False:
        print('Aguardando...\n')
        time.sleep(1)
    ligarUsb()
    while flag1 == True:
        while ser.in_waiting > 0:
            ml_raw = ser.read(2)
            print('buff: ', ml_raw)
            ml = ((ml_raw[0] << 8) | ml_raw[1])
            print('ml: ', ml)
            ser.flush()

            newMl= ml/10
            newMlStr= "{:.2f}".format(newMl)
            contagemReais=precoLitroGasolinha*newMl
            contagemReaisStr="{:.2f}".format(precoLitroGasolinha*newMl)
            #abast="Abastecendo"
            if contagemReais<reais and newMl<litros:
                atualizacaoLcd(contagemReais,contagemReaisStr,newMl,newMlStr)

    abast="Abastecido"
    #reaisStr="{:.2f}".format(reais)
    #litrosStr="{:.2f}".format(litros)
    atualizacaoLcd(reais,reaisStr,litros,litrosStr)
    desligarUsb()
    ser.close()

    ser=serial.Serial('/dev/ttyS0',115200,bytesize=serial.EIGHTBITS,parity=serial.PARITY_NONE,stopbits=serial.STOPBITS_ONE, timeout=3)
    time_in = time.time()
    while True:
        if ser.in_waiting > 0:
            print("inicio leitura assinatura")
            response = ser.read(256)
            if response[0] == 0x00:
                ser.flush()
                response = ser.read(256)
            print('Rec: ', [hex(x) for x in response])
            assinatura = ''.join(format(i, '02x') for i in response)
            while tentativas<3:
                if assinatura =="031516":
                     GPIO.output(19,1)
                     ser.write(bytearray(int(num, 16) for num in buf))
                     print('sended: ', buf)
                     GPIO.output(19,0)
                     time_in = time.time()
                     while True:
                         if ser.in_waiting > 0:
                             print("inicio leitura")
                             response = ser.read(256)
                             if response[0] == 0x00:
                                 ser.flush()
                                 response = ser.read(256)
                             print('Rec: ', [hex(x) for x in response])
                             assinatura = ''.join(format(i, '02x') for i in response)
                             break
                     tentativas+=1
                     print(tentativas)
                else:
                    break
            break
        time_out = time.time()
        if (time_out - time_in) > 20:
            print("TIMEOUT")
            break

    if assinatura != "031516":
        GPIO.output(19,1)
        chavePublica='getPublicKeyIssuer\n'
        buf2=[hex(ord(caractere)) for caractere in chavePublica]
        ser.write(bytearray(int(num, 16) for num in buf2))
        print('sended: ', buf2)
        GPIO.output(19,0)
        time_in = time.time()
        while True:
            if ser.in_waiting > 0:
                print("inicio leitura")
                response = ser.read(256)
                if response[0] == 0x00:
                    ser.flush()
                    response = ser.read(256)
                print('Rec: ', [hex(x) for x in response])
                chavePublica=''.join(format(i, '02x') for i in response)

                dados = {'dado': dado, 'assinatura':assinatura, 'chavepublica':chavePublica}
                print(dados)
                try:
                    response = requests.post(enderecoVerificarAssinatura, json=dados, timeout=10)
                    if response.status_code == 200:
                        resposta=response.text
                        read_resposta = json.loads(resposta)
                        status=read_resposta['status']
                        print(status)
                except requests.exceptions.RequestException as e:
                    print(e)
                break
            time_out = time.time()
            if (time_out - time_in) > 20:
                print("TIMEOUT")
                break
    else:
        print("Erro na Transmissão de dados!!")
    ser.close()

def abastecimentoBomba1(litros, reais, mylcd):
   Contador(litros, reais, mylcd, precoLitroGasolinha)

def button_callback_gasolina(channel):
    global pad1,web,selected_lcd
    if pad1==True:
        selected_lcd=None
        t = Thread(target=somaLitrosGasolina, args=(vetorGasolinaPad,litros,mylcd0, litrosTotalGasolina))
        t.start()
        pad1=False
        print(pad1)
    if web==True:
        select_lcd=None
        t = Thread(target=somaLitrosGasolina, args=(vetor4,litros,mylcd0, litrosTotalGasolina))
        t.start()
        web=False
        print("WEB")
        print(web)

def abastecimento(channel):
    global flag1
    estado=GPIO.input(channel)
    if estado==GPIO.LOW:
         flag1=False
    else:
         flag1=True

############# ----------------- ####################

########## SÓ A WEB USA ####################

def escolherPagar(ind,modo):
   mylcd0.lcd_clear()
   reset(vetor3, vetor4, mylcd0,ind,modo)

def inserirValorNaBomba(vetor,vetor4, mylcd):
   k = 19
   numero = float(''.join(vetor4[:-2] + ['.'] + vetor4[-2:]))
   if numero<10:
       for j in range(3):
           if k == 17:
               k -= 1
           mylcd.lcd_display_string(vetor[j],1, k)
           k -= 1
   elif numero<100:
       for j in range(4):
           if k == 17:
               k -= 1
           mylcd.lcd_display_string(vetor[j],1, k)
           k -= 1
   elif numero<1000:
       for j in range(5):
           if k == 17:
               k -= 1
           mylcd.lcd_display_string(vetor[j],1, k)
           k -= 1
   else:
       for j in range(6):
           if k == 17:
               k -= 1
           mylcd.lcd_display_string(vetor[j],1, k)
           k -= 1

def inserirValorNaBombaLitros(vetor, mylcd):
   numero = float(''.join(vetor[:-2] + ['.'] + vetor[-2:]))
   if numero<10:
       k=16
       for j in range(3):
           if k == 17:
               k += 1
           mylcd.lcd_display_string(vetor[j],2, k)
           k += 1
   elif numero<100:
       k=15
       for j in range(4):
           if k == 17:
               k += 1
           mylcd.lcd_display_string(vetor[j],2, k)
           k += 1
   elif numero<1000:
       k=14
       for j in range(5):
           if k == 17:
               k += 1
           mylcd.lcd_display_string(vetor[j],2, k)
           k += 1
   else:
       k=13
       for j in range(6):
           if k == 17:
               k += 1
           mylcd.lcd_display_string(vetor[j],2, k)
           k += 1

def startAbastecimento(mylcd):
   global vetor4
   valor=request.form.get('valor')
   vetor4 = [str(caractere) for caractere in valor if caractere.isdigit()]
   n = 6 - len(vetor4)
   vetor3=vetor4[::-1]+ ["0"]*n
   print(vetor4)
   print(vetor3)

   inserirValorNaBomba(vetor3, vetor4,mylcd)
   mylcd.lcd_display_string("Litros:",2)
   strReais = "".join(vetor4)
   reais = float(strReais)/100
   return reais

def startAbastecimentoLitros(mylcd):
   global vetor4
   valor=request.form.get('valor')
   numero = "{:.2f}".format(float(valor.replace(',', '.')))
   print(numero)
   vetorLitro = list(numero.replace('.', ''))
   print(vetorLitro)

   newValor = "{:.2f}".format(float(numero)*precoLitroGasolinha)
   vetor4 = [str(caractere) for caractere in str(newValor) if caractere.isdigit()]
   n = 6 - len(vetor4)
   vetor3=vetor4[::-1]+ ["0"]*n
   print(vetor4)
   print(vetor3)

   inserirValorNaBombaLitros(vetorLitro, mylcd)
   mylcd.lcd_display_string("R$:",1)
   strReais = "".join(vetor4)
   reais = float(strReais)/100
   return reais

############# ----------------- ####################

########## SÓ O PAD USA ####################

def inserir(vetor,vetorGasolinaPad,key,ind):
    vetor.insert(0,key)
    vetorGasolinaPad.append(key)
    vetor.pop()
    numero = float(''.join(vetorGasolinaPad[:-2] + ['.'] + vetorGasolinaPad[-2:]))
    print(numero)
    k = 19
    if numero<10:
        for j in range(3):
            if k == 17:
                k -= 1

            selected_lcd.lcd_display_string(vetor[j],ind, k)
            k -= 1
        print(vetor)
        print(vetorGasolinaPad)
    elif numero<100:
        for j in range(4):
            if k == 17:
                k -= 1

            selected_lcd.lcd_display_string(vetor[j],ind, k)
            k -= 1
        print(vetor)
        print(vetorGasolinaPad)
    elif numero<1000:
        for j in range(5):
            if k == 17:
                k -= 1

            selected_lcd.lcd_display_string(vetor[j],ind, k)
            k -= 1
        print(vetor)
        print(vetorGasolinaPad)
    else:
        for j in range(6):
            if k == 17:
                k -= 1

            selected_lcd.lcd_display_string(vetor[j],ind, k)
            k -= 1
        print(vetor)
        print(vetorGasolinaPad)

def reset(vetor, vetor2, mylcd,ind, modo):
    for i in range(len(vetor)):
         vetor[i] = "0"
    vetor2.clear()
    for indice in range(4):
        indiceAtual= indice +16
        elemento = vetor[indice]
        mylcd.lcd_display_string(elemento,ind, indiceAtual)
    mylcd.lcd_display_string(".",ind, 17)
    mylcd.lcd_display_string(modo,ind, 0)
    mylcd.lcd_display_string("R$/L:",4,0)
    mylcd0.lcd_display_string(str(precoLitroGasolinha),4,16)

def printKey(key):
  global selected_lcd,bombaGasolinaEmUso,pad1,botoes_travados,f2,vetorGasolinaPad
  print(key)

  if bombaGasolinaEmUso==True:
        botoes_travados = ["ESC","F1","F2","0","1","2","3","4","5","6","7","8","9","ENTER"]
        if key in botoes_travados:
            return

  if not vetorGasolinaPad and not vetorLitrosPad:
      botoes_travados=["ENTER"]
      if key in botoes_travados:
          return

  if key == "F1":
    f2=False
    selected_lcd = mylcd0
    selected_lcd.lcd_clear()
    reset(vetor, vetorGasolinaPad, selected_lcd,1,modoR)

  if key=="F2":
    f2=True
    selected_lcd = mylcd0
    selected_lcd.lcd_clear()
    reset(vetorLitros, vetorLitrosPad,selected_lcd,2,modoL)

  if selected_lcd is not None:
    if f2==False:
        if (key=="1" or key=="2" or key=="3" or key=="4" or key=="5" or key=="6" or key=="7" or key=="8" or key=="9" or key=="0"):
            if selected_lcd ==mylcd0:
                inserir(vetor,vetorGasolinaPad,key,1)
    if f2==True:
        if (key=="1" or key=="2" or key=="3" or key=="4" or key=="5" or key=="6" or key=="7" or key=="8" or key=="9" or key=="0"):
            if selected_lcd ==mylcd0:
                inserir(vetorLitros,vetorLitrosPad,key,2)

    if (key == "ENTER"):
        if f2==False:
            selected_lcd.lcd_display_string("Litros:",2)
            abastecimentoBomba1(litros,valorAbastecimento(vetorGasolinaPad),selected_lcd)
            if selected_lcd ==mylcd0:
                if valorAbastecimento(vetorGasolinaPad)< precoLitroGasolinha/2:
                    selected_lcd.lcd_clear()
                    selected_lcd.lcd_display_string("Valor Invalido",1, 0)
                    time.sleep(2)
                    selected_lcd.lcd_clear()

                    selected_lcd.lcd_display_string("R$/L:",4,0)
                    selected_lcd.lcd_display_string(str(precoLitroGasolinha),4,16)
                    selected_lcd=None
                else:
                    pad1=True
                    bombaGasolinaEmUso=True

        if f2==True:
            selected_lcd.lcd_display_string("R$:",1)
            if selected_lcd ==mylcd0:
                litrosInt = int(''.join(vetorLitrosPad))
                litrosTotalGasolina = float(litrosInt/100)
                print(litrosTotalGasolina)
                
                valorL='%.2f'%(precoLitroGasolinha *litrosTotalGasolina)
                vetorGasolinaPad = list(str(valorL).replace('.', ''))
                abastecimentoBomba1(litros,valorAbastecimento(vetorGasolinaPad),selected_lcd)
                if litrosTotalGasolina < 0.5:
                    selected_lcd.lcd_clear()
                    selected_lcd.lcd_display_string("Valor Invalido",1, 0)
                    time.sleep(2)
                    selected_lcd.lcd_clear()

                    selected_lcd.lcd_display_string("R$/L:",4,0)
                    selected_lcd.lcd_display_string(str(precoLitroGasolinha),4,16)
                    selected_lcd=None
                else:
                    pad1=True
                    bombaGasolinaEmUso=True

    if (key == "ESC"):
        if selected_lcd ==mylcd0:
            if f2==False:
                selected_lcd.lcd_clear()
                reset(vetor, vetorGasolinaPad, selected_lcd,1,modoR)
            if f2==True:
                selected_lcd.lcd_clear()
                reset(vetorLitros, vetorLitrosPad, selected_lcd,2,modoL)

keypad.registerKeyPressHandler(printKey)
GPIO.add_event_detect(27,GPIO.RISING,callback=button_callback_gasolina,bouncetime=1000)
GPIO.add_event_detect(22,GPIO.BOTH,callback=abastecimento, bouncetime=100)

############# ----------------- ####################

if __name__ == '__main__':
    app.run(host = '0.0.0.0', port='5005')
    try:
      while(True):
        time.sleep(0.2)
    except:
        keypad.cleanup()
