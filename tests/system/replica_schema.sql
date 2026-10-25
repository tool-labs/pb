-- Minimal stand-in for the parts of the dewiki replica (dewiki_p) that pb uses.
-- Column types follow MediaWiki's schema (user names are binary there).

CREATE TABLE `user` (
  `user_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `user_name` varbinary(255) NOT NULL DEFAULT '',
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `user_name` (`user_name`)
) ENGINE=InnoDB DEFAULT CHARSET=binary;

CREATE TABLE `block_target` (
  `bt_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `bt_user` int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (`bt_id`)
) ENGINE=InnoDB DEFAULT CHARSET=binary;
