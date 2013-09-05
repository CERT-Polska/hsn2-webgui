ALTER TABLE `hsn2`.`app_schedule` ADD COLUMN `cron_expression` VARCHAR(150) NULL DEFAULT NULL;
ALTER TABLE `hsn2`.`app_schedule` ADD COLUMN `status` INT NULL DEFAULT NULL;

-- SET SQL_SAFE_UPDATES=0; -- you can uncomment this if you are running in mysql safe updates mode
UPDATE `hsn2`.`app_schedule` SET `cron_expression` = '*/30 * * * *', `scheduled_start` = NULL, `status` = 3 WHERE `frequency` = 6; -- every half hour
UPDATE `hsn2`.`app_schedule` SET `cron_expression` = '* */1 * * *', `scheduled_start` = NULL, `status` = 3 WHERE `frequency` = 5; -- every hour
UPDATE `hsn2`.`app_schedule` SET `cron_expression` = cast( concat_ws(' ', minute(`scheduled_start`), hour(`scheduled_start`), '* * *' )  AS char ), `scheduled_start` = NULL, `status` = 3 WHERE `frequency` = 2; -- every day
UPDATE `hsn2`.`app_schedule` SET `cron_expression` = cast( concat_ws(' ', minute(`scheduled_start`), hour(`scheduled_start`), '* *', weekday(`scheduled_start`) )  AS char ), `scheduled_start` = NULL, `status` = 3 WHERE `frequency` = 3; -- every week
UPDATE `hsn2`.`app_schedule` SET `cron_expression` = cast( concat_ws(' ', minute(`scheduled_start`), hour(`scheduled_start`), dayofmonth(`scheduled_start`),'* *' )  AS char ), `scheduled_start` = NULL, `status` = 3 WHERE `frequency` = 4; -- every month
UPDATE `hsn2`.`app_schedule` SET `status` = 7 WHERE `frequency` = 1; -- run once
UPDATE `hsn2`.`app_schedule` SET `status` = 7 WHERE `is_enabled` = FALSE; -- is disabled
UPDATE `hsn2`.`app_schedule` SET `status` = 5 WHERE `is_deleted` = TRUE; -- is deleted 

ALTER TABLE `hsn2`.`app_schedule` 
DROP COLUMN `last_scheduled`,
DROP COLUMN `last_submit`,
DROP COLUMN `frequency`,
DROP COLUMN `is_deleted`,
DROP COLUMN `is_enabled`;
