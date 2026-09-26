# Wi-SUN runtime logic, loaded after initial setup to keep each source module smaller.
import gc
import machine
import ure
import utime

RUNTIME_CMD_RETRY_LIMIT = 6  # Consecutive command timeouts before starting recovery.


def recover_runtime(reason, ipv6_addr):
    # EVENT 25 alone does not prove that meter traffic has recovered.
    saw_event24 = reason == 'EVENT 24'
    for attempt in range(1, RUNTIME_RECOVERY_RETRIES + 1) :
        print('>> Runtime recovery reason=' + reason + ' attempt=' + str(attempt))
        uart.write('SKTERM\r\n')
        term_result, term_line = wait_uart_response('runtime SKTERM', UART_CMD_TIMEOUT, ('OK', 'FAIL ER10', 'FAIL', 'EVENT 24'))
        if term_result == 0 or term_result == 1 :
            print('>> Runtime SKTERM result=' + ('OK' if term_result == 0 else 'FAIL ER10'))
            uart.write('SKJOIN ' + ipv6_addr + '\r\n')
            join_result, join_line = wait_uart_response('runtime SKJOIN', PANA_JOIN_TIMEOUT, ('EVENT 25', 'EVENT 24', 'FAIL'))
            if join_result == 0 :
                print('>> Runtime SKJOIN EVENT 25; checking E7')
                command = bytes('SKSENDTO 1 {0} 0E1A 1 {1:04X} '.format(ipv6_addr, len(GET_NOW_P)), 'utf-8')
                uart.write(command)
                uart.write(GET_NOW_P)
                e7_started = utime.time()
                while (utime.time() - e7_started) < RUNTIME_E7_TIMEOUT :
                    if uart.any() != 0 :
                        line = uart.readline()
                        if line is not None :
                            received = line.strip()
                            if ure.match('ERXUDP', received) :
                                u.read(line)
                                if u.type == 'E7' :
                                    print('>> Runtime recovery E7 confirmed attempt=' + str(attempt))
                                    return True, False
                                print('>> Runtime E7 wait ERXUDP type=' + str(u.type))
                            else :
                                print('>> Runtime E7 wait RX=' + str(received[:120]))
                                if ure.match('EVENT 24', received) or ure.match('FAIL', received) :
                                    if ure.match('EVENT 24', received) :
                                        saw_event24 = True
                                    break
                    utime.sleep(0.1)
                print('>> Runtime E7 missing after EVENT 25 attempt=' + str(attempt))
            else :
                print('>> Runtime SKJOIN result=' + ('EVENT 24' if join_result == 1 else 'FAIL' if join_result == 2 else 'timeout'))
                if join_result == 1 :
                    saw_event24 = True
        else :
            if term_result == 3 :
                saw_event24 = True
            print('>> Runtime SKTERM result=' + ('EVENT 24' if term_result == 3 else 'FAIL' if term_result == 2 else 'timeout'))
        if attempt < RUNTIME_RECOVERY_RETRIES :
            utime.sleep(RUNTIME_RECOVERY_COOLDOWN)
    return False, saw_event24


def run(app):
    # Functions in this module use the same devices and settings as the main script.
    shared = globals()
    for name in ('u', 'uart', 'wait_uart_response', 'reset_for_scan',
                 'GET_NOW_P', 'GET_TOTAL_POWER_30', 'UART_CMD_TIMEOUT',
                 'PANA_JOIN_TIMEOUT', 'RUNTIME_E7_TIMEOUT',
                 'RUNTIME_RECOVERY_COOLDOWN', 'RUNTIME_RECOVERY_RETRIES',
                 'ipv6Addr', 'np_interval', 'am_interval', 'RES_TOUT', 'TIMEOUT',
                 'ESP_NOW_F', 'AM_ID_1', 'AM_WKEY_1', 'AM_ID_2', 'AM_WKEY_2',
                 'am_now_power', 'am_total_power', 'espnow',
                 'draw_lcd', 'draw_am_status'):
        if name in app:
            shared[name] = app[name]
    np_tc = app['np_tc']
    tp_tc = app['tp_tc']
    am_tc = app['am_tc']
    cmd_tc = app['cmd_tc']
    tp_f = app['tp_f']
    cmd_w = app['cmd_w']
    cmd_rc = app['cmd_rc']
    rejoin_tc = app['rejoin_tc']
    Am_st_1 = app['Am_st_1']
    Am_st_2 = app['Am_st_2']
    data_mute = app['data_mute']

    while True:
        recovery_reason = None
        # スマートメーターへのコマンド送信処理
        if cmd_w == False : # コマンド重送しない為の排他制御
            if ((utime.time() - tp_tc) >= (30 * 60)) or ((not tp_f) and ((utime.time() - tp_tc) >= 10)) : # 30分毎に積算電力量要求コマンド送信（受信出来ない時のコマンド再送信は10秒開ける）
                command = bytes('SKSENDTO 1 {0} 0E1A 1 {1:04X} '.format(ipv6Addr, len(GET_TOTAL_POWER_30)), 'utf-8')
                uart.write(command)
                uart.write(GET_TOTAL_POWER_30)
                print('>> [GET_TOTAL_POWER_30] cmd send ' + str(utime.time()))
                tp_tc = utime.time()
                tp_f = False	# 積算電力量要求を出したので、受信してない扱いでFalse
                cmd_tc = utime.time()
                cmd_w = True	# コマンド送信したので排他状態にする
                cmd_rc += 1
                utime.sleep(0.5)
            elif (utime.time() - np_tc) >= np_interval : # 瞬時電力計測値要求コマンド送信（コマンド頻度が多くなるので、受信できない時のコマンド再送信処理は無し）
                command = bytes('SKSENDTO 1 {0} 0E1A 1 {1:04X} '.format(ipv6Addr, len(GET_NOW_P)), 'utf-8')
                uart.write(command)
                uart.write(GET_NOW_P)
                print('>> [GET_NOW_P] cmd send ' + str(utime.time()))
                np_tc = utime.time()
                cmd_tc = utime.time()
                cmd_w = True # コマンド送信したので排他状態にする
                cmd_rc += 1
                utime.sleep(0.5)

        # スマートメーターからの受信処理
        if cmd_w == True or uart.any() != 0 :
            line = None # UDPデータの受信処理
            u.type = ''
            if uart.any() != 0 :
                line = uart.readline()
                if line is not None :
                    u.read(line)
                    if ure.match('EVENT 24', line.strip()) :
                        print('>> Runtime RX EVENT 24')
                        recovery_reason = 'EVENT 24'
                    elif ure.match('FAIL', line.strip()) :
                        print('>> Runtime RX ' + str(line.strip()[:120]))
            #        print(line) #全ログ取得デバッグ用
                if u.type == 'E7' :    # [E7]なら受信データは瞬時電力計測値
                    cmd_w = False      # 受信したらコマンド排他フラグ解除
                    cmd_rc = 0         # コマンド再送カウンタもゼロに
                    rejoin_tc = 0
                    data_mute = False
                    app['data_mute'] = data_mute
                    draw_lcd()
                    if ESP_NOW_F : # ESP NOW一斉同報発信を使う場合
                        espnow.send(id=2, data=str('NPD=' + str(u.instant_power[0])))
                    if (utime.time() - am_tc) >= am_interval :
                        if (AM_ID_1 is not None) and (AM_WKEY_1 is not None) :  # Ambient_1が設定されてる場合
                            try :                                               # ネットワーク不通発生などで例外エラー終了されない様に try except しとく
                                rn = am_now_power.send({'d1': u.instant_power[0]})
                                print('Ambient send OK!  / ' + str(rn.status_code) + ' / ' + str(Am_st_1))
                                Am_st_1 = 2
                                app['Am_st_1'] = Am_st_1
                                am_tc = utime.time()
                                rn.close()
                            except :
                                print('Ambient send ERR! / ' + str(Am_st_1))
                                Am_st_1 = 3
                                app['Am_st_1'] = Am_st_1
                            draw_am_status()
                elif u.type == 'EA72' : # [EA72]なら受信データは積算電力量
                    cmd_w = False       # 受信したらコマンド排他フラグ解除
                    cmd_rc = 0          # コマンド再送カウンタもゼロに
                    tp_f = True         # 積算電力量を受信したのでTrue
                    if ESP_NOW_F :      # ESP NOW一斉同報発信を使う場合
                        espnow.send(id=2, data=str('TPD=' + str(u.total_power[0]) + '/' + u.total_power[1]))
                    if (AM_ID_2 is not None) and (AM_WKEY_2 is not None) :  # Ambient_2が設定されてる場合
                        try :                                               # ネットワーク不通発生などで例外エラー終了されない様に try except しとく
                            rt = am_total_power.send({'created': u.total_power[1], 'd1': u.total_power[0]})
                            print('Ambient send OK! (Total Power) / ' + str(rt.status_code) + ' / ' + str(Am_st_2))
                            Am_st_2 = 2
                            app['Am_st_2'] = Am_st_2
                            rt.close()
                        except :
                            print('Ambient send ERR! (Total Power) / ' + str(Am_st_2))
                            Am_st_2 = 3
                            app['Am_st_2'] = Am_st_2
                        draw_am_status()

            if cmd_w and recovery_reason is None and cmd_rc <= RUNTIME_CMD_RETRY_LIMIT : # コマンド再送信回数内なら
                if (utime.time() - cmd_tc) >= RES_TOUT : # コマンド送信後の受信待ちタイムアウトを越えたら、コマンド再送信
                    print(">> cmd response timeout " + str(utime.time()))
                    cmd_w = False  # コマンド排他フラグ解除
                    cmd_tc = utime.time()
            elif cmd_w and recovery_reason is None and cmd_rc > RUNTIME_CMD_RETRY_LIMIT :
                recovery_reason = 'command retry limit count=' + str(cmd_rc)

        # スマートメーターから長期間受信出来なかった場合の処理
        if not u.instant_power[1] == '' :
            if (utime.time() - u.instant_power[1]) >= TIMEOUT : # スマートメーターから瞬時電力計測値の応答が一定時間無い場合は電力値表示のみオフ
                data_mute = True
                app['data_mute'] = data_mute
                draw_lcd()
            if recovery_reason is None and (utime.time() - max(u.instant_power[1], rejoin_tc)) >= (TIMEOUT * 4) : # 再接続後は新しいE7を待つ猶予を設ける
                recovery_reason = 'stale instant power age=' + str(utime.time() - u.instant_power[1]) + 's'

        if recovery_reason is not None :
            recovered, saw_event24 = recover_runtime(recovery_reason, ipv6Addr)
            if recovered :
                cmd_w = False
                cmd_rc = 0
                cmd_tc = utime.time()
                np_tc = cmd_tc
                rejoin_tc = 0
                data_mute = False
                app['data_mute'] = data_mute
                draw_lcd()
            else :
                if saw_event24 :
                    reset_for_scan('runtime EVENT 24 after recovery attempts')
                print('>> Reset reason=runtime recovery exhausted reason=' + recovery_reason)
                machine.reset()
                raise RuntimeError('Runtime recovery exhausted: ' + recovery_reason)

        utime.sleep(0.1)
        gc.collect()
