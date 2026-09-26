# Display and button callbacks share the live application dictionary.
import utime

_app = None

def bind(app):
    global _app
    _app = app


# Plus/2でバックライト制御が違うので対応（PlusはAXPでバックライト制御、Plus2はAXP無し）
def bkl_level( a: int ):
    if (a > 100):   # 輝度指定は0～100まで
        a = 100

    if 'axp' in _app:   # M5StickC無印、またはM5StickC Plusの場合
        _app['axp'].setLcdBrightness(a)
    else :                   # M5StickC Plus2の場合
        _app['M5pwr'].brightness(a)


# BEEP音鳴らしスレッド関数
def beep_sound():
    while True:
        data_mute = _app['data_mute']
        u = _app['u']
        AMPERE_LIMIT = _app['AMPERE_LIMIT']
        AMPERE_RED = _app['AMPERE_RED']
        beep = _app['beep']
        speaker = _app['speaker']
        if data_mute or (u.instant_power[0] == 0) : # タイムアウトで表示ミュートされてるか、初期値のままならpass
            pass
        else :
            if (u.instant_power[0] >= (AMPERE_LIMIT * AMPERE_RED * 100)) and (beep == True) :  # 警告閾値超えでBEEP ONなら
                speaker.tone(220, 200)
                utime.sleep(2)
        utime.sleep(0.1)


# 表示OFFボタン処理スレッド関数
def buttonA_wasPressed():
    lcd_mute = _app['lcd_mute']

    if lcd_mute :
        lcd_mute = False
    else :
        lcd_mute = True

    _app['lcd_mute'] = lcd_mute
    if lcd_mute == True :
        bkl_level(0)        # バックライト輝度調整（OFF）
    else :
        bkl_level(_app['bkl_ON'])    # バックライト輝度調整（ON）


# BEEP音ボタン処理スレッド関数
def buttonA_wasDoublePress():
    beep = _app['beep']

    if beep :
        beep = False
    else :
        beep = True

    _app['beep'] = beep
    draw_lcd()


# 画面向き切替ボタン処理スレッド関数
def buttonB_wasPressed():
    Disp_angle = _app['Disp_angle']

    if Disp_angle == 1 :
        Disp_angle = 0
    else :
        Disp_angle = 1

    _app['Disp_angle'] = Disp_angle
    draw_lcd()


# 表示モード切替時の描画処理関数
def draw_lcd():
    lcd = _app['lcd']
    m5type = _app['m5type']
    lcd.clear()

    if m5type == 1 : # M5StickCPlus/2のみ
        draw_beep_status()

    draw_am_status()
    draw_w()


# 瞬間電力値表示処理関数
def draw_w():
    lcd = _app['lcd']
    u = _app['u']
    Disp_angle = _app['Disp_angle']
    m5type = _app['m5type']
    lcd_mute = _app['lcd_mute']
    data_mute = _app['data_mute']
    AMPERE_LIMIT = _app['AMPERE_LIMIT']
    AMPERE_RED = _app['AMPERE_RED']
    bkl_ON = _app['bkl_ON']

    if data_mute or (u.instant_power[0] == 0) : # タイムアウトで表示ミュートされてるか、初期値のままなら電力値非表示（黒文字化）
        fc = lcd.BLACK
    else :
        if u.instant_power[0] >= (AMPERE_LIMIT * AMPERE_RED * 100) :  # 警告閾値超え時は文字が赤くなる
            fc = lcd.RED
            if lcd_mute == True :   # 閾値超え時はLCD ON
                bkl_level(bkl_ON)   # バックライト輝度調整（ON）
        else :
            fc = lcd.WHITE
            if lcd_mute == True :
                bkl_level(0)        # バックライト輝度調整（OFF）

    # M5StickC(無印)向け
    if m5type == 0 :
        if Disp_angle == 0 : # [0:電源ボタンが上]
            lcd.font(lcd.FONT_DejaVu18, rotate = 270) # 単位(W)の表示
            lcd.print('W', 60, 30, fc)
            lcd.font(lcd.FONT_DejaVu40, rotate = 270) # 瞬間電力値の表示
            lcd.print(str(u.instant_power[0]), 25, 24 + (len(str(u.instant_power[0]))* 24), fc)
        if Disp_angle == 1 : # [1:電源ボタンが下]
            lcd.font(lcd.FONT_DejaVu18, rotate = 90) # 単位(W)の表示
            lcd.print('W', 20, 125, fc)
            lcd.font(lcd.FONT_DejaVu40, rotate = 90) # 瞬間電力値の表示
            lcd.print(str(u.instant_power[0]), 56, 128 - (len(str(u.instant_power[0]))* 24), fc)

    # M5StickCPlus/2向け
    if m5type == 1 :
        # 文字列の表示揃え用の位置オフセット
        if len(str(u.instant_power[0])) > 3 :
            str_offset = 0
        else :
            str_offset = 32

        if Disp_angle == 0 : # [0:電源ボタンが上]
            lcd.font(lcd.FONT_DejaVu24, rotate = 270) # 単位(W)の表示
            lcd.print('W', 72, 30, fc)
            lcd.font(lcd.FONT_DejaVu56, rotate = 270) # 瞬間電力値の表示
            lcd.print(str(u.instant_power[0]), 45, 185 - str_offset, fc)
        if Disp_angle == 1 : # [1:電源ボタンが下]
            lcd.font(lcd.FONT_DejaVu24, rotate = 90) # 単位(W)の表示
            lcd.print('W', 63, 210, fc)
            lcd.font(lcd.FONT_DejaVu56, rotate = 90) # 瞬間電力値の表示
            lcd.print(str(u.instant_power[0]), 92, 55 + str_offset, fc)


# BEEPステータスマーカー表示処理関数（M5StickCPlus/2のみ）
def draw_beep_status():
    lcd = _app['lcd']
    beep = _app['beep']
    Disp_angle = _app['Disp_angle']
    if beep == True :
        if Disp_angle == 0 :    # [0:電源ボタンが上、1:電源ボタンが下]
            lcd.roundrect(1, 1, 20, 50, 10, 0x66e6ff, 0x2acf00)
            lcd.font(lcd.FONT_Default, rotate = 270)
            lcd.text(6, 40, "BEEP", 0x000000)
        if Disp_angle == 1 :
            lcd.roundrect(114, 189, 20, 50, 10, 0x66e6ff, 0x2acf00)
            lcd.font(lcd.FONT_Default, rotate = 90)
            lcd.text(128, 198, "BEEP", 0x000000)


# Ambient通信ステータスマーカー表示処理関数
def draw_am_status():
    lcd = _app['lcd']
    Am_st_1 = _app['Am_st_1']
    Am_st_2 = _app['Am_st_2']
    m5type = _app['m5type']
    Disp_angle = _app['Disp_angle']
    # Ambientステータス [0:設定無し、1:設定有＆初回通信待ち、2:設定有＆通信OK、3:設定有＆通信NG]

    # Ambient設定 1 (瞬間電力値)のステータス表示関係
    if Am_st_1 > 0 :  # Ambient設定有ならAmbient通信ステータスマーカー描画
        if Am_st_1 == 1 :     # Ambient設定有＆初回通信待ち ⇒ 白枠、中黒
            c_o = lcd.WHITE
            c_f = lcd.BLACK
        elif Am_st_1 == 2 :   # Ambient設定有＆通信OK ⇒ 白枠、中緑
            c_o = lcd.WHITE
            c_f = lcd.GREEN
        elif Am_st_1 == 3 :   # Ambient設定有＆通信NG ⇒ 白枠、中赤
            c_o = lcd.WHITE
            c_f = lcd.RED

        c_offset = 3    # Ambient通信ステータスマーカーの画面端からのオフセット量

        # M5StickC(無印)向け
        if m5type == 0 :
            c_r = 7
            if Disp_angle == 0 :    # [0:電源ボタンが上、1:電源ボタンが下]
                c_x = 0 + c_r + c_offset
                c_y = 159 - c_r - c_offset
            if Disp_angle == 1 :
                c_x = 79 - c_r - c_offset
                c_y = 0 + c_r + c_offset
        # M5StickCPlus向け
        if m5type == 1 :
            c_r = 10
            if Disp_angle == 0 :    # [0:電源ボタンが上、1:電源ボタンが下]
                c_x = 0 + c_r + c_offset
                c_y = 239 - c_r - c_offset
            if Disp_angle == 1 :
                c_x = 134 - c_r - c_offset
                c_y = 0 + c_r + c_offset

        # Ambient設定 1 のステータス描画
        lcd.circle(c_x, c_y, c_r, c_o, c_f)

    # Ambient設定 2 (30分毎積算電力値)のステータス表示関係
    if Am_st_2 > 0 :  # Ambient設定有ならAmbient通信ステータスマーカー描画
        if Am_st_2 == 1 :     # Ambient設定有＆初回通信待ち ⇒ 白枠、中黒
            c_o = lcd.WHITE
            c_f = lcd.BLACK
        elif Am_st_2 == 2 :   # Ambient設定有＆通信OK ⇒ 白枠、中緑
            c_o = lcd.WHITE
            c_f = lcd.GREEN
        elif Am_st_2 == 3 :   # Ambient設定有＆通信NG ⇒ 白枠、中赤
            c_o = lcd.WHITE
            c_f = lcd.RED

        c_offset = 3    # Ambient通信ステータスマーカーの画面端からのオフセット量

        # M5StickC(無印)向け
        if m5type == 0 :
            c_r = 7
            if Disp_angle == 0 :    # [0:電源ボタンが上、1:電源ボタンが下]
                c_x = 0 + c_r + c_offset
                c_y = 159 - c_r - c_offset - c_r * 2 - 3
            if Disp_angle == 1 :
                c_x = 79 - c_r - c_offset
                c_y = 0 + c_r + c_offset + c_r * 2 + 3
        # M5StickCPlus向け
        if m5type == 1 :
            c_r = 10
            if Disp_angle == 0 :    # [0:電源ボタンが上、1:電源ボタンが下]
                c_x = 0 + c_r + c_offset
                c_y = 239 - c_r - c_offset - c_r * 2 - 3
            if Disp_angle == 1 :
                c_x = 134 - c_r - c_offset
                c_y = 0 + c_r + c_offset + c_r * 2 + 3

        # Ambient設定 2 のステータス描画
        lcd.circle(c_x, c_y, c_r, c_o, c_f)
