#include "app_config.h"

#define WHO_AM_I_REG 0x75
#define PWR_MGMT_1_REG 0x6B
#define CONFIG_REG 0x1A
#define GYRO_CONFIG_REG 0x1B
#define ACCEL_CONFIG_REG 0x1C
#define ACCEL_XOUT_H_REG 0x3B

int16_t Accel_X_RAW, Accel_Y_RAW, Accel_Z_RAW;
int16_t Gyro_X_RAW, Gyro_Y_RAW, Gyro_Z_RAW;
int16_t Accel_X_OFFSET = 0, Accel_Y_OFFSET = 0, Accel_Z_OFFSET = 0;
int16_t Gyro_X_OFFSET = 0, Gyro_Y_OFFSET = 0, Gyro_Z_OFFSET = 0;

AppStatus MPU6050_Init(void) {
    uint8_t check, Data;
    if (HAL_I2C_IsDeviceReady(&hi2c1, MPU6050_ADDR, 2, 100) != HAL_OK) return STATUS_ERROR;
    HAL_I2C_Mem_Read(&hi2c1, MPU6050_ADDR, WHO_AM_I_REG, 1, &check, 1, 100);
    if (check != 0x68) return STATUS_ERROR;
    Data = 0x00; HAL_I2C_Mem_Write(&hi2c1, MPU6050_ADDR, PWR_MGMT_1_REG, 1, &Data, 1, 100);
    Data = 0x05; HAL_I2C_Mem_Write(&hi2c1, MPU6050_ADDR, CONFIG_REG, 1, &Data, 1, 100);
    Data = 0x00; HAL_I2C_Mem_Write(&hi2c1, MPU6050_ADDR, GYRO_CONFIG_REG, 1, &Data, 1, 100);
    HAL_I2C_Mem_Write(&hi2c1, MPU6050_ADDR, ACCEL_CONFIG_REG, 1, &Data, 1, 100);
    return STATUS_OK;
}

void MPU6050_Read_All(void) {
    uint8_t Rec_Data[14];
    HAL_I2C_Mem_Read(&hi2c1, MPU6050_ADDR, ACCEL_XOUT_H_REG, 1, Rec_Data, 14, 100);
    Accel_X_RAW = (int16_t)(Rec_Data[0] << 8 | Rec_Data[1]);
    Accel_Y_RAW = (int16_t)(Rec_Data[2] << 8 | Rec_Data[3]);
    Accel_Z_RAW = (int16_t)(Rec_Data[4] << 8 | Rec_Data[5]);
    Gyro_X_RAW  = (int16_t)(Rec_Data[8] << 8 | Rec_Data[9]);
    Gyro_Y_RAW  = (int16_t)(Rec_Data[10] << 8 | Rec_Data[11]);
    Gyro_Z_RAW  = (int16_t)(Rec_Data[12] << 8 | Rec_Data[13]);
}

void MPU6050_Calibrate(void) {
    HAL_UART_Transmit(&huart2, (uint8_t*)"[Sensor] Calibrando... Mantenha imovel.\r\n", 41, HAL_MAX_DELAY);
    long ax=0, ay=0, az=0, gx=0, gy=0, gz=0;
    for(int i=0; i<500; i++) {
        MPU6050_Read_All();
        ax+=Accel_X_RAW; ay+=Accel_Y_RAW; az+=Accel_Z_RAW;
        gx+=Gyro_X_RAW; gy+=Gyro_Y_RAW; gz+=Gyro_Z_RAW;
        HAL_Delay(2);
    }
    Accel_X_OFFSET=ax/500; Accel_Y_OFFSET=ay/500; Accel_Z_OFFSET=az/500;
    Gyro_X_OFFSET=gx/500; Gyro_Y_OFFSET=gy/500; Gyro_Z_OFFSET=gz/500;
}