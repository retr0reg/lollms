"""
project: lollms
file: lollms_binding_infos.py 
author: ParisNeo
description: 
    This module contains a set of FastAPI routes that provide information about the Lord of Large Language and Multimodal Systems (LoLLMs) Web UI
    application. These routes are specific to bindings

"""
from fastapi import APIRouter, Request
from pydantic import BaseModel
import pkg_resources
from lollms.server.elf_server import LOLLMSElfServer
from lollms.binding import BindingBuilder, InstallOption
from ascii_colors import ASCIIColors
from lollms.utilities import load_config, trace_exception, gc
from pathlib import Path
from typing import List
import json

class ReloadBindingParams(BaseModel):
    binding_name: str

class BindingInstallParams(BaseModel):
    name: str


router = APIRouter()
lollmsElfServer = LOLLMSElfServer.get_instance()


# ----------------------------------- Listing -----------------------------------------
@router.get("/list_bindings")
def list_bindings():
    """
    List all available bindings in the Lollms server.

    Returns:
        List[str]: A list of binding names.
    """    
    bindings_dir = lollmsElfServer.lollms_paths.bindings_zoo_path  # replace with the actual path to the models folder
    bindings=[]
    for f in bindings_dir.iterdir():
        if f.stem!="binding_template":
            card = f/"binding_card.yaml"
            if card.exists():
                try:
                    bnd = load_config(card)
                    bnd["folder"]=f.stem
                    installed = (lollmsElfServer.lollms_paths.personal_configuration_path/"bindings"/f.stem/f"config.yaml").exists()
                    bnd["installed"]=installed
                    ui_file_path = f/"ui.html"
                    if ui_file_path.exists():
                        with ui_file_path.open("r") as file:
                            text_content = file.read()
                            bnd["ui"]=text_content
                    else:
                        bnd["ui"]=None
                    disclaimer_file_path = f/"disclaimer.md"
                    if disclaimer_file_path.exists():
                        with disclaimer_file_path.open("r") as file:
                            text_content = file.read()
                            bnd["disclaimer"]=text_content
                    else:
                        bnd["disclaimer"]=None
                    icon_file = lollmsElfServer.find_extension(lollmsElfServer.lollms_paths.bindings_zoo_path/f"{f.name}", "logo", [".svg",".gif",".png"])
                    if icon_file is not None:
                        icon_path = Path(f"bindings/{f.name}/logo{icon_file.suffix}")
                        bnd["icon"]=str(icon_path)

                    bindings.append(bnd)
                except Exception as ex:
                    print(f"Couldn't load backend card : {f}\n\t{ex}")
    return bindings

# ----------------------------------- Reloading ----------------------------------------
@router.post("/reload_binding")
def reload_binding( params: ReloadBindingParams):
    print(f"Roloading binding selected : {params.binding_name}")
    lollmsElfServer.config["binding_name"]=params.binding_name
    try:
        if lollmsElfServer.binding:
            lollmsElfServer.binding.destroy_model()
        lollmsElfServer.binding = None
        lollmsElfServer.model = None
        for per in lollmsElfServer.mounted_personalities:
            if per is not None:
                per.model = None
        gc.collect()
        lollmsElfServer.binding = BindingBuilder().build_binding(lollmsElfServer.config, lollmsElfServer.lollms_paths, InstallOption.INSTALL_IF_NECESSARY, lollmsCom=lollmsElfServer)
        lollmsElfServer.model = None
        lollmsElfServer.config.save_config()
        ASCIIColors.green("Binding loaded successfully")
    except Exception as ex:
        ASCIIColors.error(f"Couldn't build binding: [{ex}]")
        trace_exception(ex)
        return {"status":False, 'error':str(ex)}
    

# ----------------------------------- Installation/Uninstallation/Reinstallation ----------------------------------------

@router.post("/install_binding")
def install_binding(data:BindingInstallParams):
    """Install a new binding on the server.
    
    Args:
        data (BindingInstallParams): Parameters required for installation.
        format:
            name: str : the name of the binding
    
    Returns:
        dict: Status of operation.
    """
    ASCIIColors.info(f"- Reinstalling binding {data.name}...")
    try:
        lollmsElfServer.info("Unmounting binding and model")
        lollmsElfServer.info("Reinstalling binding")
        old_bn = lollmsElfServer.config.binding_name
        lollmsElfServer.config.binding_name = data.name
        lollmsElfServer.binding =  BindingBuilder().build_binding(lollmsElfServer.config, lollmsElfServer.lollms_paths, InstallOption.FORCE_INSTALL, lollmsCom=lollmsElfServer)
        lollmsElfServer.success("Binding installed successfully")
        del lollmsElfServer.binding
        lollmsElfServer.binding = None
        lollmsElfServer.config.binding_name = old_bn
        if old_bn is not None:
            lollmsElfServer.binding =  BindingBuilder().build_binding(lollmsElfServer.config, lollmsElfServer.lollms_paths, lollmsCom=lollmsElfServer)
            lollmsElfServer.model = lollmsElfServer.binding.build_model()
            for per in lollmsElfServer.mounted_personalities:
                if per is not None:
                    per.model = lollmsElfServer.model
        return {"status": True}
    except Exception as ex:
        lollmsElfServer.error(f"Couldn't build binding: [{ex}]")
        trace_exception(ex)
        return {"status":False, 'error':str(ex)}

@router.post("/reinstall_binding")
def reinstall_binding(data:BindingInstallParams):
    """Reinstall an already installed binding on the server.
    
    Args:
        data (BindingInstallParams): Parameters required for reinstallation.
        format:
            name: str : the name of the binding
    
    Returns:
        dict: Status of operation.
    """    
    ASCIIColors.info(f"- Reinstalling binding {data.name}...")
    try:
        ASCIIColors.info("Unmounting binding and model")
        del lollmsElfServer.binding
        lollmsElfServer.binding = None
        gc.collect()
        ASCIIColors.info("Reinstalling binding")
        old_bn = lollmsElfServer.config.binding_name
        lollmsElfServer.config.binding_name = data.name
        lollmsElfServer.binding =  BindingBuilder().build_binding(lollmsElfServer.config, lollmsElfServer.lollms_paths, InstallOption.FORCE_INSTALL, lollmsCom=lollmsElfServer)
        lollmsElfServer.success("Binding reinstalled successfully")
        lollmsElfServer.config.binding_name = old_bn
        lollmsElfServer.binding =  BindingBuilder().build_binding(lollmsElfServer.config, lollmsElfServer.lollms_paths, lollmsCom=lollmsElfServer)
        lollmsElfServer.model = lollmsElfServer.binding.build_model()
        for per in lollmsElfServer.mounted_personalities:
            if per is not None:
                per.model = lollmsElfServer.model
        
        return {"status": True}
    except Exception as ex:
        ASCIIColors.error(f"Couldn't build binding: [{ex}]")
        trace_exception(ex)
        return {"status":False, 'error':str(ex)}

@router.post("/unInstall_binding")
def unInstall_binding(data:BindingInstallParams):
    """Uninstall an installed binding from the server.
    
    Args:
        data (BindingInstallParams): Parameters required for uninstallation.
        format:
            name: str : the name of the binding
    Returns:
        dict: Status of operation.
    """    
    ASCIIColors.info(f"- Reinstalling binding {data.name}...")
    try:
        ASCIIColors.info("Unmounting binding and model")
        if lollmsElfServer.binding is not None:
            del lollmsElfServer.binding
            lollmsElfServer.binding = None
            gc.collect()
        ASCIIColors.info("Uninstalling binding")
        old_bn = lollmsElfServer.config.binding_name
        lollmsElfServer.config.binding_name = data.name
        lollmsElfServer.binding =  BindingBuilder().build_binding(lollmsElfServer.config, lollmsElfServer.lollms_paths, InstallOption.NEVER_INSTALL, lollmsCom=lollmsElfServer)
        lollmsElfServer.binding.uninstall()
        ASCIIColors.green("Uninstalled successful")
        if old_bn!=lollmsElfServer.config.binding_name:
            lollmsElfServer.config.binding_name = old_bn
            lollmsElfServer.binding =  BindingBuilder().build_binding(lollmsElfServer.config, lollmsElfServer.lollms_paths, lollmsCom=lollmsElfServer)
            lollmsElfServer.model = lollmsElfServer.binding.build_model()
            for per in lollmsElfServer.mounted_personalities:
                if per is not None:
                    per.model = lollmsElfServer.model
        else:
            lollmsElfServer.config.binding_name = None
        if lollmsElfServer.config.auto_save:
            ASCIIColors.info("Saving configuration")
            lollmsElfServer.config.save_config()
            
        return {"status": True}
    except Exception as ex:
        ASCIIColors.error(f"Couldn't build binding: [{ex}]")
        trace_exception(ex)
        return {"status":False, 'error':str(ex)}     
    
# ----------------------------------- Bet binding settings ----------------------------------------

@router.get("/get_active_binding_settings")
def get_active_binding_settings():
    print("- Retreiving binding settings")
    if lollmsElfServer.binding is not None:
        if hasattr(lollmsElfServer.binding,"binding_config"):
            return lollmsElfServer.binding.binding_config.config_template.template
        else:
            return {}
    else:
        return {}

def set_active_binding_settings(data):
    print("- Setting binding settings")
    
    if lollmsElfServer.binding is not None:
        if hasattr(lollmsElfServer.binding,"binding_config"):
            for entry in data:
                if entry["type"]=="list" and type(entry["value"])==str:
                    try:
                        v = json.loads(entry["value"])
                    except:
                        v= ""
                    if type(v)==list:
                        entry["value"] = v
                    else:
                        entry["value"] = [entry["value"]]
            lollmsElfServer.binding.binding_config.update_template(data)
            lollmsElfServer.binding.binding_config.config.save_config()
            lollmsElfServer.binding.settings_updated()
            if lollmsElfServer.config.auto_save:
                ASCIIColors.info("Saving configuration")
                lollmsElfServer.config.save_config()
            return {'status':True}
        else:
            return {'status':False}
    else:
        return {'status':False}