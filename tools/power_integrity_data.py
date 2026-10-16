"""Shared component and pin data for the 2026-10-14 power-integrity revision.

The schematic and layout stages consume this one table so fields and pin maps
cannot drift. Coordinates are absolute KiCad coordinates.

Revised 2026-10-15: motor cutoff lowered to 6.35 V coast / 6.75 V enable,
R30 raised to 100 k, VREF decoupling split between U6 (C25) and the drivers
(C28), a 100 uF hold-up capacitor (C30) on ESP_3V3, test pads TP10/TP11, and
placements that keep the SPI and encoder corridors clear (see
layout/power-integrity/README.md).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCH_ROOT = '/fefb2c5c-cd05-4562-bf27-32a51f81fd04'

def part(lib, value, footprint, mpn, datasheet, description, sch, pcb, nets):
    return dict(lib=lib, fields=dict(Value=value, Footprint=footprint, MPN=mpn,
                Datasheet=datasheet, Description=description), sch=sch, pcb=pcb, nets=nets)

RFP = 'Resistor_SMD:R_0805_2012Metric'
CFP = 'Capacitor_SMD:C_0603_1608Metric'
TPFP = 'TestPoint:TestPoint_Pad_D1.5mm'
RT_DATASHEET = 'https://www.mouser.com/datasheet/2/447/PYu_RT_1_to_0_01_RoHS_L_12-1995645.pdf'
PARTS = {
    'U6': part('Pixy-M2:TLV3012BDBV', 'TLV3012B', 'Package_TO_SOT_SMD:SOT-23-6',
        'TLV3012BIDBVR', 'https://www.ti.com/lit/ds/symlink/tlv3012.pdf',
        'Independent motor UVLO with power-on reset; REF also supplies the driver current reference.',
        (157.48, 35.56, 0), (148.6, 152.0, 0),
        {'1':'MOTOR_OK','2':'GND','3':'MOTOR_UVLO','4':'MOTOR_VREF','5':'MOTOR_VREF','6':'ESP_3V3'}),
    'U7': part('Pixy-M2:SN74LV4066APW', 'SN74LV4066APW', 'Package_SO:TSSOP-14_4.4x5mm_P0.65mm',
        'SN74LV4066APWR', 'https://www.ti.com/lit/ds/symlink/sn74lv4066a.pdf',
        'Four normally-open motor input switches. Disabled by U6, independent of firmware and USB.',
        (200.66, 39.37, 0), (149.0, 146.0, 0),
        {'1':'GPIO39','2':'DRV_A_IN1','3':'DRV_A_IN2','4':'GPIO40',
         '5':'MOTOR_OK','6':'MOTOR_OK','7':'GND','8':'GPIO41','9':'DRV_B_IN1',
         '10':'DRV_B_IN2','11':'GPIO42','12':'MOTOR_OK','13':'MOTOR_OK','14':'ESP_3V3'}),
    'U8': part('Power_Management:LM66100DCK', 'LM66100DCK', 'Package_TO_SOT_SMD:SOT-363_SC-70-6',
        'LM66100DCKR', 'https://www.ti.com/lit/ds/symlink/lm66100.pdf',
        'USB-priority buck isolation. Q2 blocks its forward body diode while disabled; Q3 follows ST.',
        (256.54, 33.02, 0), (150.4, 94.9, 0),
        {'1':'BUCK_3V3','2':'GND','3':'USB_PRIORITY','4':None,'5':'BUCK_ENABLE','6':'BUCK_PASS'}),
    'Q2': part('Transistor_FET:AO3401A', 'AO3401A', 'Package_TO_SOT_SMD:SOT-23', 'AO3401A',
        'https://www.aosmd.com/sites/default/files/res/datasheets/AO3401A.pdf',
        'P-FET source at BUCK_PASS, drain at ESP_3V3. Opposes the LM66100 body diode for off-state isolation.',
        (285.75, 33.02, 0), (153.75, 95.0, 270),
        {'1':'BUCK_GATE','2':'BUCK_PASS','3':'ESP_3V3'}),
    'Q3': part('Transistor_BJT:MMBT3904', 'MMBT3904', 'Package_TO_SOT_SMD:SOT-23', 'MMBT3904LT1G',
        'https://www.onsemi.com/pdf/datasheet/mmbt3904lt1-d.pdf',
        'ST high-impedance enables Q2 through this NPN; ST low turns Q2 off.',
        (270.51, 58.42, 0), (157.2, 92.6, 90),
        {'1':'BUCK_ENABLE','2':'GND','3':'BUCK_GATE'}),
}

def resistor(ref, value, sch, pcb, a, b, mpn=''):
    precision = '0.1%' in value
    PARTS[ref] = part('Device:R', value, RFP, mpn, RT_DATASHEET if precision else '',
        'Motor UVLO: thin film 0.1%, <=25 ppm/C.' if precision else '1% thick-film resistor, <=100 ppm/C.',
        sch, pcb, {'1':a,'2':b})

# Motor cutoff: enable 6.75 V, coast 6.35 V nominal (U6 REF 1.242 V).
resistor('R24','100k 0.1%',(140.97,27.94,0),(145.3,155.3,0),'VBAT','MOTOR_UVLO','RT0805BRD07100KL')
resistor('R25','23.2k 0.1%',(140.97,45.72,0),(148.0,155.9,270),'MOTOR_UVLO','GND','RT0805BRD0723K2L')
resistor('R26','825k 0.1%',(168.91,22.86,90),(144.6,152.0,90),'MOTOR_UVLO','MOTOR_OK','RT0805BRD07825KL')
resistor('R27','100k 1%',(181.61,57.15,0),(157.5,146.5,90),'MOTOR_OK','GND')
resistor('R28','10k 1%',(233.68,49.53,0),(154.3,89.6,180),'DEVKIT_5V','USB_PRIORITY')
resistor('R29','82k 1%',(233.68,60.96,0),(150.7,89.6,180),'USB_PRIORITY','GND')
# 100 k: Q3 only has to sink R31's 33 uA, so 26 uA of base drive saturates it
resistor('R30','100k 1%',(250.19,53.34,0),(150.4,97.6,0),'BUCK_3V3','BUCK_ENABLE')
resistor('R31','100k 1%',(289.56,52.07,0),(153.75,92.0,0),'BUCK_PASS','BUCK_GATE')

for ref,value,sch,pcb,a in [
    ('C23','0.1uF 16V',(147.32,57.15,0),(152.2,149.9,0),'ESP_3V3'),
    ('C24','0.1uF 16V',(215.9,59.69,90),(155.0,143.0,0),'ESP_3V3'),
    # C25 + C28 = 6.9 nF nominal: within the TLV3012B REF's 10 nF load limit
    ('C25','2.2nF 16V',(170.18,54.61,0),(151.7,152.6,90),'MOTOR_VREF'),
    ('C26','1uF 16V',(250.19,73.66,0),(150.2,92.4,0),'BUCK_3V3'),
    ('C27','0.1uF 16V',(156.21,57.15,0),(149.8,155.7,270),'MOTOR_UVLO'),
    ('C28','4.7nF 16V',(58.42,276.86,0),(115.0,120.2,0),'MOTOR_VREF'),
]:
    PARTS[ref] = part('Device:C', value, CFP, '', '', 'X7R ceramic capacitor.',
                      sch, pcb, {'1':a,'2':'GND'})

# Hold-up for the USB-unplug handover (U8 turn-on ~40 us): ~45 uF effective at 3.3 V.
PARTS['C30'] = part('Device:C', '100uF 6.3V X5R', 'Capacitor_SMD:C_1206_3216Metric',
    'GRM31CR60J107ME39L', 'https://www.murata.com/en-us/products/productdetail?partno=GRM31CR60J107ME39L',
    'ESP_3V3 hold-up across the USB-to-buck handover. X5R 1206; ~45 uF at 3.3 V bias.',
    (266.7,74.93,0), (153.6, 156.6, 0), {'1':'ESP_3V3','2':'GND'})

for ref,value,desc,sch,pcb in [
    ('TP10','MOTOR_OK','Test point, U6 motor-enable output',(147.32,124.46,0),(132.0,156.6,0)),
    ('TP11','MOTOR_VREF','Test point, 1.242 V driver current reference',(162.56,124.46,0),(124.9,117.0,0)),
]:
    PARTS[ref] = part('Connector:TestPoint', value, TPFP, '', '', desc, sch, pcb, {'1':value})

# Existing parts this revision moves on the PCB only (ref -> (old, new)).
PCB_MOVES = {'TP2': ('TestPoint:TestPoint_Pad_D1.5mm', (151.0, 95.0, 0.0), (148.4, 86.6, 0)),
             'TP3': ('TestPoint:TestPoint_Pad_D1.5mm', (154.5, 91.5, 0.0), (151.8, 86.6, 0))}

DRIVER_NETS = {('U4','3'):'DRV_A_IN1',('U4','2'):'DRV_A_IN2',
               ('U5','3'):'DRV_B_IN1',('U5','2'):'DRV_B_IN2',
               ('U4','4'):'MOTOR_VREF',('U5','4'):'MOTOR_VREF'}
BUCK_PADS = {('U3','1'),('L1','2'),('C7','1'),('C11','1')}
OLD_INPUTS = {'/GPIO39':'/DRV_A_IN1','/GPIO40':'/DRV_A_IN2',
              '/GPIO41':'/DRV_B_IN1','/GPIO42':'/DRV_B_IN2'}
CURRENT_FIELDS = dict(Value='1kOhm 1%', Footprint=RFP, MPN='RC0805FR-071KL',
    Datasheet='https://yageogroup.com/component-documentation/download/specsheet/RC0805FR-071KL',
    Description='ITRIP nominal 0.828A from U6 REF=1.242V; IPROPI scale 1.5V/A.')
