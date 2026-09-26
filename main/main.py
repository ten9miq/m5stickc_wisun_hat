# Wi-SUN HAT（BP35A1用）のサンプルプログラム
# ver 0.0.1a (2024/5/5 Update)
# @rin-ofumi
#
# 確認した機種 (検証時のUIFlow Ver)
# - M5StickC (v1.13.4)
# - M5StickC Plus (v1.13.4
# - M5StickC Plus2 (v1.13.4)
from m5stack import *
import machine
import gc
import utime
import ure
import uos
import _thread
import wifiCfg
import ntptime
import wisun_udp


#### 変数・関数初期値定義 ####

# 固定値
GET_COEFFICIENT         = b'\x10\x81\x00\x01\x05\xFF\x01\x02\x88\x01\x62\x01\xD3\x00'           #D3     *積算電力量係数の要求
GET_TOTAL_POWER_UNIT    = b'\x10\x81\x00\x01\x05\xFF\x01\x02\x88\x01\x62\x01\xE1\x00'           #E1     *積算電力量単位の要求
GET_NOW_PA              = b'\x10\x81\x00\x01\x05\xFF\x01\x02\x88\x01\x62\x02\xE7\x00\xE8\x00'   #E7&E8  *瞬時電力計測値＆瞬時電流計測値（T/R相）の要求
GET_NOW_P               = b'\x10\x81\x00\x01\x05\xFF\x01\x02\x88\x01\x62\x01\xE7\x00'           #E7     *瞬時電力計測値の要求
GET_TOTAL_POWER_30      = b'\x10\x81\x00\x01\x05\xFF\x01\x02\x88\x01\x62\x01\xEA\x00'           #EA     *30分毎更新の積算電力量の要求

# 変数宣言
SCAN_COUNT              = 6     # ActiveScan試行回数
SCAN_RETRY_COOLDOWN     = 60    # ActiveScan全試行失敗後の待機（秒）
UART_CMD_TIMEOUT        = 10    # BP35A1のコマンド応答待ち（秒）
SCAN_RESULT_TIMEOUT     = 45    # スキャン完了イベント待ち（秒）
PANA_JOIN_TIMEOUT       = 60    # PANA認証イベント待ち（秒）
UART_CMD_RETRIES        = 2     # コマンド応答が無い場合の送信回数
RUNTIME_RECOVERY_RETRIES = 3   # Runtime PANA recovery attempts before MCU reset
RUNTIME_RECOVERY_COOLDOWN = 5  # Delay between recovery attempts (seconds)
RUNTIME_E7_TIMEOUT      = 30   # Wait for a real E7 response after EVENT 25 (seconds)
channel                 = ''
panid                   = ''
macadr                  = ''
lqi                     = ''

Am_st_1                 = 0     # Ambient設定 1 のステータス   [0:無し(WiFiも未使用になる)、1:設定有＆初回通信待ち、2:設定有＆通信OK、3:設定有＆通信NG]
Am_st_2                 = 0     # Ambient設定 2 のステータス   [0:無し(WiFiも未使用になる)、1:設定有＆初回通信待ち、2:設定有＆通信OK、3:設定有＆通信NG]
Disp_angle              = 0     # グローバル 画面方向 [0:電源ボタンが上、1:電源ボタンが下]
lcd_mute                = False # グローバル
data_mute               = False # グローバル
beep                    = True  # グローバル
m5type                  = 0     # 画面サイズ種別 [0:M5StickC、1: M5StickCPlus/2]
bkl_ON                  = 40    # 画面ON時のバックライト輝度 [0 ～ 100]
np_interval             = 5     # 瞬間電力値の要求サイクル（秒）※最短でも5秒以上が望ましい
am_interval             = 30    # Ambientへデータを送るサイクル（秒））※Ambientは3000件/日までなので、丸1日分持たせるには30秒以上にする

AM_ID_1                 = None  # Ambient設定 1 のID（別途の設定ファイルで指定するのでこれはダミー）
AM_WKEY_1               = None  # Ambient設定 1 のライトキー（別途の設定ファイルで指定するのでこれはダミー）
AM_ID_2                 = None  # Ambient設定 2 のID（別途の設定ファイルで指定するのでこれはダミー）
AM_WKEY_2               = None  # Ambient設定 2 のライトキー（別途の設定ファイルで指定するのでこれはダミー）
ESP_NOW_F               = False # ESP_NOWを使うかの設定値のデフォルト値
RES_TOUT                = 10    # スマートメーターからのコマンド応答待ちタイムアウト（秒）のデフォルト値
TIMEOUT                 = 30    # 何らかの事情で更新が止まった時のタイムアウト（秒）のデフォルト値
AMPERE_RED              = 0.7   # 契約ブレーカー値に対し、どれくらいの使用率で赤文字化させるかのデフォルト値 （力率は無視してます）
AMPERE_LIMIT            = 30    # 契約ブレーカー値のデフォルト値


# Helper modules compile separately to reduce import-time peak memory.
import wisun_ui
gc.collect()
import wisun_setup
gc.collect()
import wisun_runtime
wisun_ui.bind(globals())
wisun_setup.bind(globals())
from wisun_ui import bkl_level, beep_sound, buttonA_wasPressed, buttonA_wasDoublePress, buttonB_wasPressed, draw_lcd, draw_w, draw_beep_status, draw_am_status
from wisun_setup import wisun_set_filechk, wisun_scan_filechk, wait_uart_response, send_uart_command, reset_for_scan


#### メインプログラムはここから（この上はプログラム内関数）####

print('heapmemory= ' + str(gc.mem_free()))


# 基本設定ファイル[wisun_set_m.txt]のチェック 無い場合は例外エラー吐いて終了する
if not wisun_set_filechk() :
    lcd.print('err!! Check [wisun_set_m.txt] and restart!!', 0, 0, lcd.WHITE)
    raise ValueError('err!! Check [wisun_set_m.txt] and restart!!')


# M5StickC/Plus機種判定
if lcd.winsize() == (80,160) :
    m5type = 0
    print('>> M5Type = M5StickC')
if lcd.winsize() == (136,241) :
    m5type = 1
    print('>> M5Type = M5StickCPlus/2')


# WiFi設定
wifiCfg.autoConnect(lcdShow=True)
lcd.clear()
lcd.print('*', 0, 0, lcd.WHITE)
print('>> WiFi init OK')


# UDPデータインスタンス生成
u = wisun_udp.udp_read()
print('>> UDP reader init OK')


# Ambientインスタンス生成
Am_st_1 = 0
if (AM_ID_1 is not None) and (AM_WKEY_1 is not None) : # Ambient_1の設定情報があった場合
    import ambient
    am_now_power = ambient.Ambient(AM_ID_1, AM_WKEY_1)
    print('>> Ambient_1 init OK')
    Am_st_1 = 1

Am_st_2 = 0
if (AM_ID_2 is not None) and (AM_WKEY_2 is not None) : # Ambient_2の設定情報があった場合
    import ambient
    am_total_power = ambient.Ambient(AM_ID_2, AM_WKEY_2)
    print('>> Ambient_2 init OK')
    Am_st_2 = 1

lcd.print('**', 0, 0, lcd.WHITE)


# BP35A1 UART設定
#uart = machine.UART(1, tx=0, rx=36) # Wi-SUN HAT rev0.1用
uart = machine.UART(1, tx=0, rx=26) # Wi-SUN HAT rev0.2用
#uart.init(115200, bits=8, parity=None, stop=1, timeout=2000)
uart.init(115200, bits=8, parity=None, stop=1, timeout=100, timeout_char=100)
lcd.print('***', 0, 0, lcd.WHITE)
print('>> UART init OK')

# UARTの送受信バッファーの塵データをクリア
utime.sleep(0.5)
if uart.any() != 0 :
    dust = uart.read()
uart.write('\r\n')
utime.sleep(1)
if uart.any() != 0 :
    dust = uart.read()
uart.write('\r\n')
utime.sleep(0.5)
print('>> UART RX/TX Data Clear!')


# BP35A1の初期設定 - コマンドエコーバックをオンにする
send_uart_command('SKSREG SFE 1\r\n', 'echo on')
print('>> BA35A1 Echo back ON set OK')
utime.sleep(0.5)


# BP35A1の初期設定 - ユーザーIDとパスワードの入手（必須では無い）
send_uart_command('SKINFO\r\n', 'module info')
print('>> BA35A1 Info OK')
utime.sleep(0.5)


# BP35A1の初期設定 - ERXUDPデータ部表示形式をASCIIへ変更（デフォはバイナリ）
mode_flg = False
_, line = send_uart_command('ROPT\r\n', 'read ASCII mode')
print(' - BP35A1 ASCII mode')

if ure.match("OK 00" , line) :
    print(' - BP35A1 Binary Mode')
    mode_flg = True
utime.sleep(0.5)

if mode_flg :
    print('>> BP35A1 ASCII mode set')
    send_uart_command('WOPT 01\r\n', 'set ASCII mode')
    print('>> BP35A1 ASCII mode set OK')
lcd.print('****', 0, 0, lcd.WHITE)


# 以前のPANAセッションを解除
# 前セッションが残ってると接続出来ない？場合の対策 前セッション無しでも、ER10が返ってくるだけ
term_result, _ = send_uart_command('SKTERM\r\n', 'clear old PANA session', ('OK', 'FAIL ER10'))
if term_result == 0 :
    print(' -Old Session Clear!')
else :
    print(' -Non Old Session')
lcd.print('*****', 0, 0, lcd.WHITE)


# B-root PASSWORDを送信
send_uart_command("SKSETPWD C " + BRPSWD + "\r\n", 'set B-root password')
print('>> BA35A1 B-root PASSWORD set OK')
lcd.print('***** *', 0, 0, lcd.WHITE)
utime.sleep(0.5)


# B-root IDを送信
send_uart_command("SKSETRBID " + BRID + "\r\n", 'set B-root ID')
print('>> BA35A1 B-root ID set OK')
lcd.print('***** **', 0, 0, lcd.WHITE)
utime.sleep(1)
gc.collect()


# Wi-SUNチャンネルスキャン（「Wi-SUN_SCAN.txt」の存在しない or 中身が異常値だった場合）
if not wisun_scan_filechk() :
    #<Channel Scan>
    scanOK = False
    s_c = 1
    while not scanOK :
        channel = ''
        panid = ''
        macadr = ''
        lqi = ''
        # ROHMのBP35A1コマンドリファレンスより
        # MODE         : 2（Paring IDあり）
        # CHANNEL_MASK : FFFFFFFF（全チャンネルのスキャン）
        # DURATION     : 6（0.624sec） [各チャンネルのスキャン時間 有効範囲:0-14 計算式:0.0096*(2^DURATION+1)sec]
        send_uart_command('SKSCAN 2 FFFFFFFF 6\r\n', 'scan command attempt=' + str(s_c))
        print('>> Activescan count:' + str(s_c) + ' start!')

        #スキャン要求1回分の受信ループ処理
        scan_res_end = False
        scan_started = utime.time()
        while not scan_res_end :
            line = None
            if uart.any() != 0 :
                line = uart.readline()
                if line is not None :
                    if ure.match("EVENT 22" , line.strip()) : # スキャン1周分が完了（見付かったかは別）
                        print('>> Activescan count:' + str(s_c) + ' done!')
                        scan_res_end = True                   # スキャンが1周完了してるのでループ抜け
                    elif ure.match("Channel:" , line.strip()) :
                        pickuptext = ure.compile(':')
                        pickt = pickuptext.split(line.strip())
                        channel = str(pickt[1].strip(), 'utf-8')
                        print(" Channel= " + str(channel))
                    elif ure.match("Pan ID:" , line.strip()) :
                        pickuptext = ure.compile(':')
                        pickt = pickuptext.split(line.strip())
                        panid = str(pickt[1].strip(), 'utf-8')
                        print(" Pan_ID= " + str(panid))
                    elif ure.match("Addr:" , line.strip()) :
                        pickuptext = ure.compile(':')
                        pickt = pickuptext.split(line.strip())
                        macadr = str(pickt[1].strip(), 'utf-8')
                        print(" MAC_Addr= " + str(macadr))
                    elif ure.match("LQI:" , line.strip()) :
                        pickuptext = ure.compile(':')
                        pickt = pickuptext.split(line.strip())
                        lqi = str(pickt[1].strip(), 'utf-8')
                        print(" LQI= " + str(lqi))
                    print(line.strip())
            utime.sleep(0.1)
            gc.collect()
            if (utime.time() - scan_started) >= SCAN_RESULT_TIMEOUT :
                print('>> UART timeout stage=scan result attempt=' + str(s_c) + ' limit=' + str(SCAN_RESULT_TIMEOUT) + 's')
                break

        # スキャン結果の全ての情報が揃ってるかチェック
        if scan_res_end and len(channel) == 2 and len(panid) == 4 and len(macadr) == 16 and len(lqi) == 2 :
            with open('/flash/Wi-SUN_SCAN.txt' , 'w') as f:
                f.write('Channel:' + str(channel) + '\r\n')
                f.write('Pan_ID:' + str(panid) + '\r\n')
                f.write('MAC_Addr:' + str(macadr) + '\r\n')
                f.write('LQI:' + str(lqi) + '\r\n')
                print('>> [Wi-SUN_SCAN.txt] maked!!')
            print('Scan All Clear!')
            scanOK = True
        else :
            print('>> Scan incomplete attempt=' + str(s_c))
            if s_c >= SCAN_COUNT :
                print('>> Active scan failed ' + str(SCAN_COUNT) + ' times; retrying in ' + str(SCAN_RETRY_COOLDOWN) + 's')
                utime.sleep(SCAN_RETRY_COOLDOWN)
                gc.collect()
                s_c = 1
            else :
                s_c += 1
lcd.print('***** ***', 0, 0, lcd.WHITE)


# PANA接続処理
while True :
    #<Channel set>
    send_uart_command("SKSREG S2 " + channel + "\r\n", 'set channel')

    #<Pan ID set>
    send_uart_command("SKSREG S3 " + panid + "\r\n", 'set PAN ID')

    #<MACアドレスをIPV6アドレスに変換>
    uart.write("SKLL64 " + macadr + "\r\n")
    ipv6_started = utime.time()
    while (utime.time() - ipv6_started) < UART_CMD_TIMEOUT :
        line = None
        if uart.any() != 0 :
            line = uart.readline()
        if line is not None :
            if len(line.strip()) == 39 :
                ipv6Addr = str(line.strip(), 'utf-8')
                print('IPv6 Addr = ' + str(ipv6Addr))
                break
        utime.sleep(0.1)
    else :
        print('>> Reset reason=UART timeout stage=IPv6 conversion')
        machine.reset()
        raise RuntimeError('IPv6 conversion timeout')

    gc.collect()
    utime.sleep(1)

    #<BP35A1のコマンドエコーバックをオフにする>
    send_uart_command('SKSREG SFE 0\r\n', 'echo off')
    print('>> BA35A1 Echo back OFF set OK')

    #<PANA接続要求>
    print('PANA authentication start!!')
    uart.write("SKJOIN " + ipv6Addr + "\r\n")
    utime.sleep(0.1)
    bConnected = False
    join_started = utime.time()
    while not bConnected and (utime.time() - join_started) < PANA_JOIN_TIMEOUT :
        line = None
        if uart.any() != 0 :
            line = uart.readline()
            print('*')
            if line is not None :
                if ure.match("EVENT 24" , line.strip()) :
                    reset_for_scan('EVENT 24 authentication failure')
                elif ure.match("EVENT 25" , line.strip()) :
                    print(">> PANA authentication OK!")
                    bConnected = True
                    utime.sleep(1)
                gc.collect()
        utime.sleep(0.1)
    if bConnected :
        break
    reset_for_scan('EVENT 25 timeout after ' + str(PANA_JOIN_TIMEOUT) + 's')
lcd.print('***** ****', 0, 0, lcd.WHITE)
gc.collect()


# ECHONET Lite 積算電力係数(COEFFICIENT)要求コマンド送信
if u.power_coefficient == 0 :
    command = bytes('SKSENDTO 1 {0} 0E1A 1 {1:04X} '.format(ipv6Addr, len(GET_COEFFICIENT)), 'utf-8')
    uart.write(command)
    uart.write(GET_COEFFICIENT)
    print('>> [GET_COEFFICIENT] cmd send ' + str(utime.time()))
    cmd_tc = utime.time()   # 受信タイムアウト用カウンタのリセット
    utime.sleep(0.5)

    while u.power_coefficient == 0 : #D3（積算電力量係数）受信待ち
        line = None
        if uart.any() != 0 :
            line = uart.readline()
            u.read(line)
            if u.type == 'D3' : # D3 積算電力量係数(COEFFICIENT)
                print(' - COEFFICIENT: ' + str(u.power_coefficient))
                break
            else:
                print(">> Unknown type " + u.type + ' ' + str(utime.time()))
        if (utime.time() - cmd_tc) >= RES_TOUT : # 受信タイムアウトした場合はコマンド非対応スマートメータと判断し、固定値とする
            print('>> response timeout! set[COEFFICIENT = 1]' + ' ' + str(utime.time()))
            u.power_coefficient = 1
        utime.sleep(0.1)

    with open('/flash/Wi-SUN_SCAN.txt' , 'a') as fc:
        fc.write('COEFFICIENT:' + str(u.power_coefficient) + '\r\n')
lcd.print('***** *****', 0, 0, lcd.WHITE)
utime.sleep(0.5)


# ECHONET Lite 積算電力単位(UNIT)要求コマンド送信
if u.power_unit == 0.0 :
    command = bytes('SKSENDTO 1 {0} 0E1A 1 {1:04X} '.format(ipv6Addr, len(GET_TOTAL_POWER_UNIT)), 'utf-8')
    uart.write(command)
    uart.write(GET_TOTAL_POWER_UNIT)
    print('>> [GET_TOTAL_POWER_UNIT] cmd send ' + str(utime.time()))
    cmd_tc = utime.time()   # 受信タイムアウト用カウンタのリセット
    utime.sleep(0.5)

    while u.power_unit == 0.0 : #E1（積算電力量単位）受信待ち
        line = None
        if uart.any() != 0 :
            line = uart.readline()
            u.read(line)
            if u.type == 'E1' : #E1 積算電力量単位(UNIT)
                print(' - UNITT: ' + str(u.power_unit))
                break
            else:
                print(">> Unknown type " + u.type + ' ' + str(utime.time()))
        if (utime.time() - cmd_tc) >= RES_TOUT : # 受信タイムアウトした場合はコマンド非対応スマートメータと判断し、固定値とする
            print('>> response timeout! set[UNIT = 0.1] ' + str(utime.time()))
            u.power_unit = 0.1
        utime.sleep(0.1)

    with open('/flash/Wi-SUN_SCAN.txt' , 'a') as fu:
        fu.write('UNIT:' + str(u.power_unit) + '\r\n')
gc.collect()
lcd.print('***** ***** *', 0, 0, lcd.WHITE)


# ESP NOW設定
if ESP_NOW_F :
    import espnow
    espnow.init(0)  # UIFlow Ver1.10.2以降への対応
    esp_mac_slave1 = '94B97EAB0B8C'
    espnow.add_peer(esp_mac_slave1, id=2)
    print('>> ESP NOW init')
lcd.print('***** ***** **', 0, 0, lcd.WHITE)

print('heapmemory= ' + str(gc.mem_free()))


# RTC設定
ntp = ntptime.client(host='jp.pool.ntp.org', timezone=9)
print('>> RTC init OK')


# 画面初期化
bkl_level(bkl_ON) # バックライト輝度調整（ON）
draw_lcd()
print('>> Disp init OK')


# BEEP音鳴らしスレッド起動
if m5type == 1 : # M5StickCPlus/2のみ
    _thread.start_new_thread(beep_sound, ())
    print('>> BEEP Sound thread ON')


# ボタン検出スレッド起動
btnA.wasPressed(buttonA_wasPressed)
btnB.wasPressed(buttonB_wasPressed)
btnA.wasDoublePress(buttonA_wasDoublePress)
print('>> Button Check thread ON')


# タイムカウンタ初期値設定
np_tc = utime.time()
tp_tc = utime.time()
am_tc = utime.time()
cmd_tc = utime.time()  # コマンド受信タイムアウト用カウンタ
tp_f = False    # 積算電力量応答の有無フラグ
cmd_w = False   # コマンド受信待機待ちフラグ（コマンド重送しない為の排他制御）Trueは受信待ち
cmd_rc = 0      # コマンド再送信回数カウンタ
rejoin_tc = 0   # 再接続後、E7を受信するまで古い計測時刻によるリセットを猶予


# 一旦、お掃除
gc.collect()
print('heapmemory= ' + str(gc.mem_free()))
print(">> Start mainloop! " + str(utime.time()))


# メインループは wisun_runtime.py に分割
wisun_runtime.run(globals())
