#ifndef APP_CONFIG_H
#define APP_CONFIG_H

#include "stm32f1xx_hal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdbool.h>

// --- CONFIGURAÇÕES DE HARDWARE ---
#define STATUS_LED_PORT GPIOB
#define STATUS_LED_PIN  GPIO_PIN_1
#define MPU6050_ADDR    0xD0
#define FLASH_STORAGE_ADDRESS 0x0800FC00

// --- CONFIGURAÇÕES DO SISTEMA ---
#define DEVICE_ID "Monitoramento_Veicular"
#define MODEM_RX_BUFFER_SIZE 512
#define MAX_SAMPLES 200
#define JSON_BUFFER_SIZE 2500

// --- DEFAULTS
#define DEFAULT_PRE_TRIGGER_SAMPLES  24
#define DEFAULT_POST_TRIGGER_SAMPLES 25
#define DEFAULT_EVENT_THRESHOLD_X    3.0f
#define DEFAULT_EVENT_THRESHOLD_Y    3.0f
#define DEFAULT_SENSOR_DELAY_MS      4

// --- CONFIGURAÇÃO DO KEEP ALIVE 
#define KEEP_ALIVE_INTERVAL_MS  (2 * 60 * 1000) // 2 Minutos em milissegundos

// --- CORES ---
#define ANSI_COLOR_RED     "\x1b[31m"
#define ANSI_COLOR_GREEN   "\x1b[32m"
#define ANSI_COLOR_YELLOW  "\x1b[33m"
#define ANSI_COLOR_CYAN    "\x1b[36m"
#define ANSI_COLOR_RESET   "\x1b[0m"
#define ANSI_COLOR_MAGENTA "\x1b[35m"

// --- ESTRUTURAS ---
typedef enum { STATUS_OK = 0, STATUS_ERROR = 1 } AppStatus;

typedef struct {
    uint16_t pre_trigger_samples;
    uint16_t post_trigger_samples;
    float    event_threshold_x;
    float    event_threshold_y;
    uint32_t sensor_read_delay_ms;
} AppConfig;

typedef struct {
    uint32_t timestamp_ms;
    float ax, ay, az;
    float gx, gy, gz;
} SensorSample;

typedef enum { STATE_MONITORING, STATE_POST_TRIGGER, STATE_PROCESSING } MonitorState;

// --- VARIÁVEIS GLOBAIS (EXTERN) ---
extern I2C_HandleTypeDef hi2c1;
extern UART_HandleTypeDef huart1;
extern UART_HandleTypeDef huart2;

extern AppConfig g_config;
extern char g_json_payload[JSON_BUFFER_SIZE];

// --- PROTÓTIPOS ---
// Core
void Normal_Mode(void);
void Sensor_Read_Mode(void);
void Configuration_Mode(void);
int User_Mode(void);
void AT_Command_PassThrough_Mode(void);
void GPS_Test_Mode(void);

// Drivers
AppStatus MPU6050_Init(void);
void MPU6050_Read_All(void);
void MPU6050_Calibrate(void);
void Modem_UART_Init(void);
void Modem_RX_Callback(void);
bool SIMCOM_Init_Sequence(void);
bool SIMCOM_Publish_Event(const char* json_payload);

// Flash
void Save_Config_To_Flash(void);
void Load_Config_From_Flash(void);
void Restore_Default_Config(void);

// Utils
void Blink_Status_LED(int count);
void Error_Handler(void);

extern int16_t Accel_X_RAW, Accel_Y_RAW, Accel_Z_RAW;
extern int16_t Gyro_X_RAW, Gyro_Y_RAW, Gyro_Z_RAW;
extern int16_t Accel_X_OFFSET, Accel_Y_OFFSET, Accel_Z_OFFSET;
extern int16_t Gyro_X_OFFSET, Gyro_Y_OFFSET, Gyro_Z_OFFSET;

#endif // APP_CONFIG_H