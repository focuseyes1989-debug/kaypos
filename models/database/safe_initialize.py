# models/database/safe_initialize.py - Add auto-fix

def safe_initialize_database() -> bool:
    """
    Safely initialize database with error handling and auto-fix.
    """
    try:
        logger.info("Initializing database...")
        
        # Check if database exists and is accessible
        db_path = "database/pos.db"
        db_dir = os.path.dirname(db_path)
        os.makedirs(db_dir, exist_ok=True)
        
        # Try to create tables
        try:
            create_tables()
            logger.info("✅ Database tables created/verified")
        except Exception as e:
            logger.error(f"❌ Failed to create tables: {e}")
            
            # Try to fix missing columns
            try:
                fix_missing_columns()
                logger.info("✅ Fixed missing columns")
            except Exception as e2:
                logger.error(f"❌ Failed to fix columns: {e2}")
                
                # Try emergency recovery
                try:
                    recovery = DatabaseRecovery()
                    success, message = recovery.auto_recover()
                    if success:
                        logger.info(f"✅ {message}")
                    return False
                except Exception as e3:
                    logger.error(f"❌ Emergency recovery failed: {e3}")
                    return False
        
        # ✅ RUN AUTO-FIX for category columns
        from models.database.auto_fix import run_auto_fix
        run_auto_fix()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False