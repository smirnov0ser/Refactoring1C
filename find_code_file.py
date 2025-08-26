#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Функция поиска файла кода по описанию объекта 1С
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class CodeFileFinder:
    """Класс для поиска файлов кода по описанию объекта 1С"""
    
    def __init__(self, base_path: str = None):
        """
        Инициализация
        
        Args:
            base_path: Базовый путь к конфигурации 1С
        """
        if base_path is None:
            # По умолчанию ищем конфигурацию в родительской директории
            current_dir = Path.cwd()
            if current_dir.name == "Refactoring1C":
                # Если мы в папке Refactoring1C, ищем конфигурацию в родительской директории
                self.base_path = current_dir.parent
            else:
                # Иначе используем текущую директорию
                self.base_path = current_dir
        else:
            self.base_path = Path(base_path)
        
        # Маппинг для первого объекта: {русское_имя: каталог, английское_имя: каталог}
        self.first_object_mapping = {
            # Регистры
            "РегистрБухгалтерии": "AccountingRegisters",
            "AccountingRegister": "AccountingRegisters",
            "РегистрНакопления": "AccumulationRegisters", 
            "AccumulationRegister": "AccumulationRegisters",
            "РегистрРасчета": "CalculationRegisters",
            "CalculationRegister": "CalculationRegisters",
            "РегистрСведений": "InformationRegisters",
            "InformationRegister": "InformationRegisters",
            
            # Основные объекты
            "БизнесПроцесс": "BusinessProcesses",
            "BusinessProcess": "BusinessProcesses",
            "Справочник": "Catalogs",
            "Catalog": "Catalogs",
            "ПланСчетов": "ChartsOfAccounts",
            "ChartOfAccounts": "ChartsOfAccounts",
            "ПланВидовРасчета": "ChartsOfCalculationTypes",
            "ChartOfCalculationTypes": "ChartsOfCalculationTypes",
            "ПланВидовХарактеристик": "ChartsOfCharacteristicTypes",
            "ChartOfCharacteristicTypes": "ChartsOfCharacteristicTypes",
            "ГруппаКоманд": "CommandGroups",
            "CommandGroup": "CommandGroups",
            "ОбщийРеквизит": "CommonAttributes",
            "CommonAttribute": "CommonAttributes",
            "ОбщаяКоманда": "CommonCommands",
            "CommonCommand": "CommonCommands",
            "ОбщаяФорма": "CommonForms",
            "CommonForm": "CommonForms",
            "ОбщийМодуль": "CommonModules",
            "CommonModule": "CommonModules",
            "ОбщаяКартинка": "CommonPictures",
            "CommonPicture": "CommonPictures",
            "ОбщийМакет": "CommonTemplates",
            "CommonTemplate": "CommonTemplates",
            "Константа": "Constants",
            "Constant": "Constants",
            "Обработка": "DataProcessors",
            "DataProcessor": "DataProcessors",
            "ОпределяемыйТип": "DefinedTypes",
            "DefinedType": "DefinedTypes",
            "ЖурналДокументов": "DocumentJournals",
            "DocumentJournal": "DocumentJournals",
            "НумераторДокументов": "DocumentNumerators",
            "DocumentNumerator": "DocumentNumerators",
            "Документ": "Documents",
            "Document": "Documents",
            "Перечисление": "Enums",
            "Enum": "Enums",
            "ПодпискаНаСобытие": "EventSubscriptions",
            "EventSubscription": "EventSubscriptions",
            "ПланОбмена": "ExchangePlans",
            "ExchangePlan": "ExchangePlans",
            "ВнешнийИсточникДанных": "ExternalDataSources",
            "ExternalDataSource": "ExternalDataSources",
            "КритерийОтбора": "FilterCriteria",
            "FilterCriterion": "FilterCriteria",
            "ФункциональнаяОпция": "FunctionalOptions",
            "FunctionalOption": "FunctionalOptions",
            "ПараметрФункциональныхОпций": "FunctionalOptionsParameters",
            "FunctionalOptionsParameter": "FunctionalOptionsParameters",
            "HTTPСервис": "HTTPServices",
            "HTTPService": "HTTPServices",
            "Интерфейс": "Interfaces",
            "Interface": "Interfaces",
            "Язык": "Languages",
            "Language": "Languages",
            "Отчет": "Reports",
            "Report": "Reports",
            "Роль": "Roles",
            "Role": "Roles",
            "РегламентноеЗадание": "ScheduledJobs",
            "ScheduledJob": "ScheduledJobs",
            "Последовательность": "Sequences",
            "Sequence": "Sequences",
            "ПараметрСеанса": "SessionParameters",
            "SessionParameter": "SessionParameters",
            "ХранилищеНастроек": "SettingsStorages",
            "SettingsStorage": "SettingsStorages",
            "ЭлементСтиля": "StyleItems",
            "StyleItem": "StyleItems",
            "Стиль": "Styles",
            "Style": "Styles",
            "Подсистема": "Subsystems",
            "Subsystem": "Subsystems",
            "Задача": "Tasks",
            "Task": "Tasks",
            "WebСервис": "WebServices",
            "WebService": "WebServices",
            "ПакетXDTO": "XDTOPackages",
            "XDTOPackage": "XDTOPackages",
            "Конфигурация": "",
            "Configuration": ""
        }
        
        # Маппинг для второго и далее объектов: {русское_имя: каталог, английское_имя: каталог}
        self.intermediate_object_mapping = {
            "Форма": "Forms",
            "Form": "Forms",
            "Подсистема": "Subsystems",
            "Subsystem": "Subsystems"
        }
        
        # Маппинг для последнего объекта: {русское_имя: [файлы], английское_имя: [файлы]}
        self.last_object_mapping = {
            "Форма": ["Ext/Form.bin", "Ext/Form/Module.bsl"],
            "Form": ["Ext/Form.bin", "Ext/Form/Module.bsl"],
            "Справка": ["Ext/Help.bin"],
            "Help": ["Ext/Help.bin"],
            "Права": ["Ext/Rights.bin"],
            "Rights": ["Ext/Rights.bin"],
            "Макет": ["Ext/Template.bin"],
            "Template": ["Ext/Template.bin"],
            "Модуль": ["Ext/Module.bsl"],
            "Module": ["Ext/Module.bsl"],
            "МодульОбъекта": ["Ext/ObjectModule.bsl"],
            "ObjectModule": ["Ext/ObjectModule.bsl"],
            "МодульМенеджера": ["Ext/ManagerModule.bsl"],
            "ManagerModule": ["Ext/ManagerModule.bsl"],
            "МодульКоманды": ["Ext/CommandModule.bsl"],
            "CommandModule": ["Ext/CommandModule.bsl"],
            "МодульНабораЗаписи": ["Ext/RecordSetModule.bsl"],
            "RecordSetModule": ["Ext/RecordSetModule.bsl"],
            "МодульКонстанты": ["Ext/ValueManagerModule.bsl"],
            "ValueManagerModule": ["Ext/ValueManagerModule.bsl"],
            "МодульВнешнегоСоединения": ["Ext/Module.bsl"],
            "ExternalConnectionModule": ["Ext/Module.bsl"],
            "МодульПриложения": ["Ext/Module.bsl"],
            "ManagedApplicationModule": ["Ext/Module.bsl"],
            "МодульОбычногоПриложения": ["Ext/Module.bsl"],
            "OrdinaryApplicationModule": ["Ext/Module.bsl"],
            "МодульНабораЗаписей": ["Ext/RecordSetModule.bsl"],
            "RecordSetModule": ["Ext/RecordSetModule.bsl"],
            "МодульСеанса": ["Ext/Module.bsl"],
            "SessionModule": ["Ext/Module.bsl"]
        }
    
    def find_code_file(self, object_path: str) -> List[str]:
        """
        Поиск файла кода по описанию объекта
        
        Args:
            object_path: Путь к объекту (например: "ОбщийМодуль.CRM_ОбработчикиСобытий.Модуль")
            
        Returns:
            Список найденных файлов
        """
        if not object_path:
            return []
        
        # Проверяем, является ли object_path прямым путем к файлу
        potential_file_path = self.base_path / object_path
        if potential_file_path.exists() and potential_file_path.is_file():
            return [str(potential_file_path)]

        # Разбиваем путь на объекты
        objects = object_path.split('.')
        if len(objects) < 2:
            return []
        
        #print(f"DEBUG: Объекты: {objects}")
        
        # Первый объект - определяет основной каталог
        first_object = objects[0]
        main_catalog = self.first_object_mapping.get(first_object)
        
        if not main_catalog:
            print(f"DEBUG: Не найден маппинг для первого объекта '{first_object}'")
            return []
        
        #print(f"DEBUG: Основной каталог: {main_catalog}")
        
        # Строим путь к основному каталогу
        current_path = self.base_path / main_catalog
        #print(f"DEBUG: Путь к основному каталогу: {current_path}")
        
        # Обрабатываем промежуточные объекты
        i = 1
        while i < len(objects) - 1:
            obj = objects[i]
            #print(f"DEBUG: Обрабатываем промежуточный объект: {obj}")
            
            # Проверяем, является ли это специальным именем
            if obj in self.intermediate_object_mapping:
                # Для специального имени используем собранный ранее путь + специальный каталог
                current_path = current_path / self.intermediate_object_mapping[obj]
                #print(f"DEBUG: Специальное имя '{obj}' → добавляем к пути: {current_path}")
                
                # Следующий объект (если он не последний) добавляем как подкаталог без проверки
                if i + 1 < len(objects) - 1:
                    next_obj = objects[i + 1]
                    subdir = self._find_subdirectory(current_path, next_obj)
                    if subdir:
                        current_path = subdir
                        #print(f"DEBUG: После специального имени найден подкаталог '{next_obj}' → {current_path}")
                    else:
                        #print(f"DEBUG: После специального имени не найден подкаталог '{next_obj}' в {current_path}")
                        return []  # Не найден подкаталог
                    i += 2  # Пропускаем два объекта
                else:
                    i += 1  # Пропускаем только текущий объект
            else:
                # Ищем подкаталог с таким именем
                subdir = self._find_subdirectory(current_path, obj)
                if subdir:
                    current_path = subdir
                    #print(f"DEBUG: Найден подкаталог '{obj}' → {current_path}")
                else:
                    #print(f"DEBUG: Не найден подкаталог '{obj}' в {current_path}")
                    return []  # Не найден подкаталог
                i += 1
        
        # Обрабатываем последний объект
        last_object = objects[-1]
        #print(f"DEBUG: Последний объект: {last_object}")
        
        # Проверяем, является ли это специальным именем
        if last_object in self.last_object_mapping:
            files_to_check = self.last_object_mapping[last_object]
            found_files = []
            
            full_path = "";
            for file_path in files_to_check:
                full_path = current_path / file_path
                #print(f"DEBUG: Проверяем файл: {full_path}")
                if full_path.exists():
                    found_files.append(str(full_path))
                    #print(f"DEBUG: Файл найден: {full_path}")
                #else:
                    #print(f"DEBUG: Файл не найден: {full_path}")
            
            if(len(found_files) == 0):
                print(f"DEBUG: Файл не найден: {full_path}")
                return []
            else:
                return found_files
            
        # Если это не специальное имя - возвращаем ошибку
        print(f"DEBUG: Последний объект '{last_object}' не является специальным именем")
        return []
    
    def _find_subdirectory(self, parent_path: Path, subdir_name: str) -> Optional[Path]:
        """
        Поиск подкаталога по имени
        
        Args:
            parent_path: Родительский путь
            subdir_name: Имя искомого подкаталога
            
        Returns:
            Путь к найденному подкаталогу или None
        """
        if not parent_path.exists() or not parent_path.is_dir():
            return None
        
        # Ищем подкаталог с точным совпадением имени
        for item in parent_path.iterdir():
            if item.is_dir() and item.name == subdir_name:
                return item
        
        return None
    


def main():
    """Основная функция"""
    finder = CodeFileFinder()

    
    # Интерактивный режим
    print("\nВведите путь к объекту для поиска (или 'quit' для выхода):")
    
    while True:
        user_input = input("> ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            break
        
        if user_input:
            result = finder.find_code_file(user_input)
            
            if result:
                print("Найденные файлы:")
                for file_path in result:
                    print(f"  - {file_path}")
            else:
                print("Файлы не найдены")


if __name__ == "__main__":
    main()
