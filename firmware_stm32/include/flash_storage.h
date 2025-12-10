#ifndef FLASH_STORAGE_H
#define FLASH_STORAGE_H

#include "app_config.h"

void Save_Config_To_Flash(void);
void Load_Config_From_Flash(void);
void Restore_Default_Config(void);

#endif // FLASH_STORAGE_H