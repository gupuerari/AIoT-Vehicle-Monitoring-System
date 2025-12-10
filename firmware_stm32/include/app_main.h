#ifndef APP_MAIN_H
#define APP_MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

// Inclui as definições de tipos do arquivo mestre
#include "app_config.h" 

// --- PROTÓTIPOS DE FUNÇÕES ---
// Apenas declare as funções públicas aqui.

void App_Init(void);
void Save_Config_To_Flash(void);

// Funções de Modos
void Normal_Mode(void);
void Sensor_Read_Mode(void);
void Configuration_Mode(void);
int User_Mode(void);
void AT_Command_PassThrough_Mode(void);
void GPS_Test_Mode(void);
void Blink_Status_LED(int count);

#ifdef __cplusplus
}
#endif

#endif // APP_MAIN_H