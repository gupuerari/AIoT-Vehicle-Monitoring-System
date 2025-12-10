#ifndef MPU6050_H
#define MPU6050_H

#include "app_config.h"

// Protótipos das funções do sensor
AppStatus MPU6050_Init(void);
void MPU6050_Read_Accel(void);
void MPU6050_Calibrate(void);

// Variáveis de dados do sensor
extern int16_t Accel_X_RAW, Accel_Y_RAW, Accel_Z_RAW;
extern int16_t Accel_X_OFFSET, Accel_Y_OFFSET, Accel_Z_OFFSET;
extern int16_t Gyro_X_RAW,Gyro_Y_RAW,Gyro_Z_RAW;
extern int16_t Gyro_X_OFFSET,Gyro_Y_OFFSET,Gyro_Z_OFFSET;

#endif // MPU6050_H