import ctypes
import mmap
import platform
import time

# Define as estruturas de dados que o Assetto Corsa escreve na memória.
# Isso é uma tradução direta da documentação oficial do SDK.

class SPageFilePhysics(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ('packetId', ctypes.c_int),
        ('gas', ctypes.c_float),
        ('brake', ctypes.c_float),
        ('fuel', ctypes.c_float),
        ('gear', ctypes.c_int),
        ('rpms', ctypes.c_int),
        ('steerAngle', ctypes.c_float),
        ('speedKmh', ctypes.c_float),
        ('velocity', ctypes.c_float * 3),
        ('accG', ctypes.c_float * 3),
        ('wheelSlip', ctypes.c_float * 4),
        ('wheelLoad', ctypes.c_float * 4),
        ('wheelsPressure', ctypes.c_float * 4),
        ('wheelAngularSpeed', ctypes.c_float * 4),
        ('tyreWear', ctypes.c_float * 4),
        ('tyreDirtyLevel', ctypes.c_float * 4),
        ('tyreCoreTemperature', ctypes.c_float * 4),
        ('camberRAD', ctypes.c_float * 4),
        ('suspensionTravel', ctypes.c_float * 4),
        ('drs', ctypes.c_float),
        ('tc', ctypes.c_float),
        ('heading', ctypes.c_float),
        ('pitch', ctypes.c_float),
        ('roll', ctypes.c_float),
        ('cgHeight', ctypes.c_float),
        ('carDamage', ctypes.c_float * 5),
        ('numberOfTyresOut', ctypes.c_int),
        ('pitLimiterOn', ctypes.c_int),
        ('abs', ctypes.c_float),
        ('kersCharge', ctypes.c_float),
        ('kersInput', ctypes.c_float),
        ('autoShifterOn', ctypes.c_int),
        ('rideHeight', ctypes.c_float * 2),
        ('turboBoost', ctypes.c_float),
        ('ballast', ctypes.c_float),
        ('airDensity', ctypes.c_float),
        ('airTemp', ctypes.c_float),
        ('roadTemp', ctypes.c_float),
        ('localAngularVel', ctypes.c_float * 3),
        ('finalFF', ctypes.c_float),
        ('performanceMeter', ctypes.c_float),
        ('engineBrake', ctypes.c_int),
        ('ersRecovery', ctypes.c_int),
        ('ersPower', ctypes.c_int),
        ('ersHeatCharging', ctypes.c_int),
        ('ersIsCharging', ctypes.c_int),
        ('kersCurrentKJ', ctypes.c_float),
        ('drsAvailable', ctypes.c_int),
        ('drsEnabled', ctypes.c_int),
        ('brakeTemp', ctypes.c_float * 4),
        ('clutch', ctypes.c_float),
        ('tyreTempI', ctypes.c_float * 4),
        ('tyreTempM', ctypes.c_float * 4),
        ('tyreTempO', ctypes.c_float * 4),
        ('isAIControlled', ctypes.c_int),
        ('tyreContactPoint', ctypes.c_float * 4 * 3),
        ('tyreContactNormal', ctypes.c_float * 4 * 3),
        ('tyreContactHeading', ctypes.c_float * 4 * 3),
        ('brakeBias', ctypes.c_float),
        ('localVelocity', ctypes.c_float * 3),
        ('P2PActive', ctypes.c_int),
        ('P2PStatus', ctypes.c_int),
        ('currentMaxRpm', ctypes.c_int),
        ('mz', ctypes.c_float * 4),
        ('fx', ctypes.c_float * 4),
        ('fy', ctypes.c_float * 4),
        ('slipRatio', ctypes.c_float * 4),
        ('slipAngle', ctypes.c_float * 4),
        ('tcinAction', ctypes.c_int),
        ('absInAction', ctypes.c_int),
        ('suspensionDamage', ctypes.c_float * 4),
        ('tyreTemp', ctypes.c_float * 4),
    ]

class SPageFileGraphic(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ('packetId', ctypes.c_int),
        ('status', ctypes.c_int),
        ('session', ctypes.c_int),
        ('currentTime', ctypes.c_wchar * 15),
        ('lastTime', ctypes.c_wchar * 15),
        ('bestTime', ctypes.c_wchar * 15),
        ('split', ctypes.c_wchar * 15),
        ('completedLaps', ctypes.c_int),
        ('position', ctypes.c_int),
        ('iCurrentTime', ctypes.c_int),
        ('iLastTime', ctypes.c_int),
        ('iBestTime', ctypes.c_int),
        ('sessionTimeLeft', ctypes.c_float),
        ('distanceTraveled', ctypes.c_float),
        ('isInPit', ctypes.c_int),
        ('currentSectorIndex', ctypes.c_int),
        ('lastSectorTime', ctypes.c_int),
        ('numberOfLaps', ctypes.c_int),
        ('tyreCompound', ctypes.c_wchar * 33),
        ('replayTimeMultiplier', ctypes.c_float),
        ('normalizedCarPosition', ctypes.c_float),
        ('carCoordinates', ctypes.c_float * 3),
        ('penaltyTime', ctypes.c_float),
        ('flag', ctypes.c_int),
        ('idealLineOn', ctypes.c_int),
        ('isInPitLine', ctypes.c_int),
        ('surfaceGrip', ctypes.c_float),
        ('mandatoryPitDone', ctypes.c_int),
        ('windSpeed', ctypes.c_float),
        ('windDirection', ctypes.c_float),
        ('isSetupMenuOpen', ctypes.c_int),
        ('mainDisplayIndex', ctypes.c_int),
        ('secondaryDisplayIndex', ctypes.c_int),
        ('TC', ctypes.c_int),
        ('TCHZ', ctypes.c_int),
        ('ABS', ctypes.c_int),
        ('ABSLEVEL', ctypes.c_float),
        ('ESP', ctypes.c_int),
        ('POWER', ctypes.c_int),
        ('RSHIFT_LIGHT_MS', ctypes.c_int),
        ('BRAKE_BIAS', ctypes.c_float),
        ('TURBO_BOOST', ctypes.c_float),
        ('ENGINE_BRAKER', ctypes.c_int),
        ('CURRENT_ENERGY', ctypes.c_int),
        ('CURRENT_STRATEGY', ctypes.c_int),
        ('MGUH_MODE', ctypes.c_int),
        ('MGUK_MODE', ctypes.c_int),
        ('ERS_BAR', ctypes.c_int),
        ('RECHARGE_BAR', ctypes.c_int),
    ]

class SPageFileStatic(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ('smVersion', ctypes.c_wchar * 15),
        ('acVersion', ctypes.c_wchar * 15),
        ('numberOfSessions', ctypes.c_int),
        ('numCars', ctypes.c_int),
        ('carModel', ctypes.c_wchar * 33),
        ('track', ctypes.c_wchar * 33),
        ('playerName', ctypes.c_wchar * 33),
        ('playerSurname', ctypes.c_wchar * 33),
        ('playerNick', ctypes.c_wchar * 33),
        ('sectorCount', ctypes.c_int),
        ('maxTorque', ctypes.c_float),
        ('maxPower', ctypes.c_float),
        ('maxRpm', ctypes.c_int),
        ('maxFuel', ctypes.c_float),
        ('suspensionMaxTravel', ctypes.c_float * 4),
        ('tyreRadius', ctypes.c_float * 4),
        ('maxTurboBoost', ctypes.c_float),
        ('airTemp', ctypes.c_float),
        ('roadTemp', ctypes.c_float),
        ('penaltiesEnabled', ctypes.c_int),
        ('aidFuelRate', ctypes.c_float),
        ('aidTireRate', ctypes.c_float),
        ('aidMechanicalDamage', ctypes.c_float),
        ('aidAllowTyreBlankets', ctypes.c_int),
        ('aidStability', ctypes.c_float),
        ('aidAutoClutch', ctypes.c_int),
        ('aidAutoBlip', ctypes.c_int),
        ('hasDRS', ctypes.c_int),
        ('hasERS', ctypes.c_int),
        ('hasKERS', ctypes.c_int),
        ('kersMaxJ', ctypes.c_float),
        ('engineManufacture', ctypes.c_wchar * 33),
        ('engineModel', ctypes.c_wchar * 33),
        ('ersPowerController', ctypes.c_int * 3),
        ('ersMode', ctypes.c_wchar * 33),
        ('isEngineInside', ctypes.c_int),
        ('isHybrid', ctypes.c_int),
        ('hasAggressiveTyreSet', ctypes.c_int),
    ]


class AssettoCorsaSharedMemory:
    def __init__(self):
        self.physics_mem = None
        self.graphics_mem = None
        self.static_mem = None
        
        self.physics_map = None
        self.graphics_map = None
        self.static_map = None
        
        self.physics = SPageFilePhysics()
        self.graphics = SPageFileGraphic()
        self.static = SPageFileStatic()
        
        if platform.system() != "Windows":
            raise Exception("Este script funciona apenas no Windows.")
            
        self._setup_mmap()

    def _setup_mmap(self):
        try:
            # Tenta mapear os arquivos de memória
            self.physics_mem = mmap.mmap(-1, ctypes.sizeof(SPageFilePhysics), "Local\\acpmf_physics", access=mmap.ACCESS_READ)
            self.graphics_mem = mmap.mmap(-1, ctypes.sizeof(SPageFileGraphic), "Local\\acpmf_graphics", access=mmap.ACCESS_READ)
            self.static_mem = mmap.mmap(-1, ctypes.sizeof(SPageFileStatic), "Local\\acpmf_static", access=mmap.ACCESS_READ)
        except FileNotFoundError:
            print("Erro: Memória compartilhada do Assetto Corsa não encontrada.")
            print("Verifique se o jogo está em execução e se [SHARED_MEMORY] ENABLED=1 está no seu 'assetto_corsa.ini'.")
            raise

    def get_physics(self):
        """Lê e retorna a estrutura de física."""
        if self.physics_mem:
            self.physics_mem.seek(0)
            data = self.physics_mem.read(ctypes.sizeof(SPageFilePhysics))
            ctypes.memmove(ctypes.addressof(self.physics), data, ctypes.sizeof(SPageFilePhysics))
            return self.physics
        return None

    def get_graphics(self):
        """Lê e retorna a estrutura de gráficos."""
        if self.graphics_mem:
            self.graphics_mem.seek(0)
            data = self.graphics_mem.read(ctypes.sizeof(SPageFileGraphic))
            ctypes.memmove(ctypes.addressof(self.graphics), data, ctypes.sizeof(SPageFileGraphic))
            return self.graphics
        return None

    def get_static(self):
        """Lê e retorna a estrutura de dados estáticos."""
        if self.static_mem:
            self.static_mem.seek(0)
            data = self.static_mem.read(ctypes.sizeof(SPageFileStatic))
            ctypes.memmove(ctypes.addressof(self.static), data, ctypes.sizeof(SPageFileStatic))
            return self.static
        return None

    def close(self):
        """Fecha os mapeamentos de memória."""
        if self.physics_mem:
            self.physics_mem.close()
        if self.graphics_mem:
            self.graphics_mem.close()
        if self.static_mem:
            self.static_mem.close()

# Para testes: se você executar este arquivo diretamente
if __name__ == "__main__":
    print("Iniciando teste do leitor de memória compartilhada do Assetto Corsa...")
    ac = AssettoCorsaSharedMemory()
    try:
        while True:
            physics = ac.get_physics()
            if physics:
                print(f"RPM: {physics.rpms} | Vel: {physics.speedKmh:.0f} km/h | AccG_Z: {physics.accG[2]:.2f}", end='\r')
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nFechando conexão.")
    finally:
        ac.close()