I_sleep = 17 * 1E-6    # A
I_on = 60 * 1E-3       # A

t_on_max = 20   # seconds
capacity = 0.9  # Ah
capacity = capacity * 60 * 60 # As


print("t_off/min | Q_off/mAh | Q_on/mAh | Q_cyc/mAh | I_avr/mA | t_run/h | t_run/days")
for t in [1, 5, 10, 15, 20]:
    t_off = t * 60  # off time

    Q_off = I_sleep * t_off / (60 * 60)
    Q_on = I_on * t_on_max / (60 * 60)
    Q_cycle = Q_off + Q_on
    t_cycle = t_on_max + t_off
    I_avr = Q_cycle / (t_cycle / (60 * 60))
    t_run = capacity / I_avr
    print(f"{t:9} | {Q_off * 1E3:9.4f} | {Q_on * 1E3:8.4f} | {Q_cycle * 1E3:9.4f} | {I_avr * 1E3:8.4f} | {t_run / (60 * 60):7.2f} | {t_run / (24 * 60 * 60):7.1f}")

