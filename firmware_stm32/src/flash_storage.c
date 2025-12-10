#include "app_config.h"

void Save_Config_To_Flash(void) {
    HAL_FLASH_Unlock();
    FLASH_EraseInitTypeDef EraseInitStruct = { .TypeErase = FLASH_TYPEERASE_PAGES, .PageAddress = FLASH_STORAGE_ADDRESS, .NbPages = 1 };
    uint32_t PageError = 0;
    if (HAL_FLASHEx_Erase(&EraseInitStruct, &PageError) != HAL_OK) { HAL_FLASH_Lock(); return; }

    uint32_t *data = (uint32_t*)&g_config;
    for (uint32_t i = 0; i < sizeof(AppConfig)/4 + 1; i++) {
        HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD, FLASH_STORAGE_ADDRESS + i*4, data[i]);
    }
    HAL_FLASH_Lock();
    HAL_UART_Transmit(&huart2, (uint8_t*)"[Flash] Salvo.\r\n", 16, HAL_MAX_DELAY);
}

void Load_Config_From_Flash(void) {
    memcpy(&g_config, (void*)FLASH_STORAGE_ADDRESS, sizeof(AppConfig));
    if (*(uint32_t*)&g_config == 0xFFFFFFFF) Restore_Default_Config();
}

void Restore_Default_Config(void) {
    g_config.pre_trigger_samples = DEFAULT_PRE_TRIGGER_SAMPLES;
    g_config.post_trigger_samples = DEFAULT_POST_TRIGGER_SAMPLES;
    g_config.event_threshold_x = DEFAULT_EVENT_THRESHOLD_X;
    g_config.event_threshold_y = DEFAULT_EVENT_THRESHOLD_Y;
    g_config.sensor_read_delay_ms = DEFAULT_SENSOR_DELAY_MS;
}