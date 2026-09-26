# Configuration and UART setup helpers.
import machine
import uos
import ure
import utime

_app = None

def bind(app):
    global _app
    _app = app


# wisun_set_m.txtの存在/中身チェック関数
def wisun_set_filechk():
    app = _app
    AMPERE_LIMIT = app['AMPERE_LIMIT']
    AMPERE_RED = app['AMPERE_RED']
    TIMEOUT = app['TIMEOUT']
    BRID = app.get('BRID', '')
    BRPSWD = app.get('BRPSWD', '')
    AM_ID_1 = app['AM_ID_1']
    AM_WKEY_1 = app['AM_WKEY_1']
    AM_ID_2 = app['AM_ID_2']
    AM_WKEY_2 = app['AM_WKEY_2']
    ESP_NOW_F = app['ESP_NOW_F']

    scanfile_flg = False
    for file_name in uos.listdir('/flash') :
        if file_name == 'wisun_set_m.txt' :
            scanfile_flg = True

    if scanfile_flg :
        print('>> found [wisun_set_m.txt] !')
        with open('/flash/wisun_set_m.txt' , 'r') as f :
            for file_line in f :
                filetxt = file_line.strip().split(':')
                if filetxt[0] == 'AMPERE_RED' :
                    if float(filetxt[1]) >= 0 and float(filetxt[1]) <= 1 :
                        AMPERE_RED = float(filetxt[1])
                        print('- AMPERE_RED: ' + str(AMPERE_RED))
                elif filetxt[0] == 'AMPERE_LIMIT' :
                    if int(filetxt[1]) >= 20 :
                        AMPERE_LIMIT = int(filetxt[1])
                        print('- AMPERE_LIMIT: ' + str(AMPERE_LIMIT))
                elif filetxt[0] == 'TIMEOUT' :
                    if int(filetxt[1]) > 0 :
                        TIMEOUT = int(filetxt[1])
                        print('- TIMEOUT: ' + str(TIMEOUT))
                elif filetxt[0] == 'BRID' :
                    BRID = str(filetxt[1])
                    print('- BRID: configured')
                elif filetxt[0] == 'BRPSWD' :
                    BRPSWD = str(filetxt[1])
                    print('- BRPSWD: configured')
                elif filetxt[0] == 'AM_ID_1' :
                    AM_ID_1 = str(filetxt[1])
                    print('- AM_ID_1: ' + str(AM_ID_1))
                elif filetxt[0] == 'AM_WKEY_1' :
                    if len(filetxt[1]) == 16 :
                        AM_WKEY_1 = str(filetxt[1])
                        print('- AM_WKEY_1: ' + str(AM_WKEY_1))
                elif filetxt[0] == 'AM_ID_2' :
                    AM_ID_2 = str(filetxt[1])
                    print('- AM_ID_2: ' + str(AM_ID_2))
                elif filetxt[0] == 'AM_WKEY_2' :
                    if len(filetxt[1]) == 16 :
                        AM_WKEY_2 = str(filetxt[1])
                        print('- AM_WKEY_2: ' + str(AM_WKEY_2))
                elif filetxt[0] == 'ESP_NOW' :
                    if int(filetxt[1]) == 0 or int(filetxt[1]) == 1 :
                        ESP_NOW_F = int(filetxt[1])
                        print('- ESP_NOW: ' + str(ESP_NOW_F))

        if len(BRID) == 32 and len(BRPSWD) == 12: # BルートIDとパスワードの桁数チェック（NGならプログラム停止）
            scanfile_flg = True
        else :
            print('>> [wisun_set_m.txt] Illegal!!')
            scanfile_flg = False

    else :
        print('>> no [wisun_set_m.txt] !')
    app['AMPERE_LIMIT'] = AMPERE_LIMIT
    app['AMPERE_RED'] = AMPERE_RED
    app['TIMEOUT'] = TIMEOUT
    app['BRID'] = BRID
    app['BRPSWD'] = BRPSWD
    app['AM_ID_1'] = AM_ID_1
    app['AM_WKEY_1'] = AM_WKEY_1
    app['AM_ID_2'] = AM_ID_2
    app['AM_WKEY_2'] = AM_WKEY_2
    app['ESP_NOW_F'] = ESP_NOW_F
    return scanfile_flg


# Wi-SUN_SCAN.txtの存在/中身チェック関数
def wisun_scan_filechk():
    app = _app
    channel = app['channel']
    panid = app['panid']
    macadr = app['macadr']
    lqi = app['lqi']
    u = app['u']

    scanfile_flg = False
    for file_name in uos.listdir('/flash') :
        if file_name == 'Wi-SUN_SCAN.txt' :
            scanfile_flg = True
    if scanfile_flg :
        print('>> found [Wi-SUN_SCAN.txt] !')
        with open('/flash/Wi-SUN_SCAN.txt' , 'r') as f :
            for file_line in f :
                filetxt = file_line.strip().split(':')
                if filetxt[0] == 'Channel' :
                    channel = filetxt[1]
                    print('- Channel: ' + channel)
                elif filetxt[0] == 'Pan_ID' :
                    panid = filetxt[1]
                    print('- Pan_ID: ' + panid)
                elif filetxt[0] == 'MAC_Addr' :
                    macadr = filetxt[1]
                    print('- MAC_Addr: ' + macadr)
                elif filetxt[0] == 'LQI' :
                    lqi = filetxt[1]
                    print('- LQI: ' + lqi)
                elif filetxt[0] == 'COEFFICIENT' :
                    u.power_coefficient = int(filetxt[1])
                    print('- COEFFICIENT: ' + str(u.power_coefficient))
                elif filetxt[0] == 'UNIT' :
                    u.power_unit = float(filetxt[1])
                    print('- UNIT: ' + str(u.power_unit))
        if len(channel) == 2 and len(panid) == 4 and len(macadr) == 16:
            scanfile_flg = True
        else :
            print('>> [Wi-SUN_SCAN.txt] Illegal!!')
            scanfile_flg = False
    else :
        print('>> no [Wi-SUN_SCAN.txt] !')
    app['channel'] = channel
    app['panid'] = panid
    app['macadr'] = macadr
    app['lqi'] = lqi
    return scanfile_flg


def wait_uart_response(stage, timeout, patterns):
    uart = _app['uart']
    # 戻り値は一致したパターンの番号と受信行。期限切れは (-1, None)。
    started = utime.time()
    while (utime.time() - started) < timeout :
        if uart.any() != 0 :
            line = uart.readline()
            if line is not None :
                received = line.strip()
                # Avoid printing credentials echoed during startup.
                if received.startswith(b'SKSETPWD') or received.startswith(b'SKSETRBID') :
                    print('>> UART RX stage=' + stage + ' credential echo')
                elif received.startswith(b'ERXUDP') :
                    print('>> UART RX stage=' + stage + ' ERXUDP ' + str(received[:120]))
                else :
                    print('>> UART RX stage=' + stage + ' ' + str(received[:120]))
                for index in range(len(patterns)) :
                    if ure.match(patterns[index], received) :
                        return index, received
        utime.sleep(0.1)
    print('>> UART timeout stage=' + stage + ' limit=' + str(timeout) + 's')
    return -1, None


def send_uart_command(command, stage, patterns=('OK',)):
    uart = _app['uart']
    UART_CMD_RETRIES = _app['UART_CMD_RETRIES']
    UART_CMD_TIMEOUT = _app['UART_CMD_TIMEOUT']
    for attempt in range(1, UART_CMD_RETRIES + 1) :
        print('>> UART stage=' + stage + ' attempt=' + str(attempt))
        uart.write(command)
        result, line = wait_uart_response(stage, UART_CMD_TIMEOUT, patterns)
        if result >= 0 :
            return result, line
    print('>> Reset reason=UART command timeout stage=' + stage)
    machine.reset()
    raise RuntimeError('UART command timeout stage=' + stage)


def reset_for_scan(reason):
    print('>> Reset reason=' + reason + ' stage=PANA join; rescan on next boot')
    if 'Wi-SUN_SCAN.txt' in uos.listdir('/flash') :
        uos.remove('/flash/Wi-SUN_SCAN.txt')
    machine.reset()
    raise RuntimeError('PANA join failed: ' + reason)
