# FreePDF Install Script
# Using NSIS (Nullsoft Scriptable Install System)

# Include Modern UI
!include "MUI2.nsh"
!include "FileFunc.nsh"

!ifdef NATIVE_PREVIEW
!define APP_NAME "FreePDF Native"
!define APP_KEY "FreePDFNative"
!define OUTPUT_FILE "FreePDF_v6.0.1_Windows_Native.exe"
!else
!define APP_NAME "FreePDF"
!define APP_KEY "FreePDF"
!define OUTPUT_FILE "FreePDF_v6.0.1.exe"
!endif

# Program Information
Name "${APP_NAME}"
OutFile "${OUTPUT_FILE}"
InstallDir "$PROGRAMFILES64\${APP_NAME}"
InstallDirRegKey HKLM "Software\${APP_KEY}" "InstallPath"
RequestExecutionLevel admin

# Version Information
VIProductVersion "6.0.1.0"
VIAddVersionKey "ProductName" "FreePDF"
VIAddVersionKey "Comments" "Free PDF Translation Tool"
VIAddVersionKey "CompanyName" "FreePDF Team"
VIAddVersionKey "FileDescription" "FreePDF Setup"
VIAddVersionKey "FileVersion" "6.0.1.0"
VIAddVersionKey "ProductVersion" "6.0.1.0"
VIAddVersionKey "InternalName" "FreePDF"
VIAddVersionKey "LegalCopyright" "© 2025 FreePDF Team"
VIAddVersionKey "OriginalFilename" "FreePDF_Setup.exe"

# UI Settings
!define MUI_ABORTWARNING
!define MUI_ICON "ui\logo\logo.ico"
!define MUI_UNICON "ui\logo\logo.ico"

# Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\FreePDF.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch FreePDF"
!insertmacro MUI_PAGE_FINISH

# Uninstall Pages
!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

# Language
!insertmacro MUI_LANGUAGE "SimpChinese"

# Install Section - Only Main Program
Section "FreePDF" SecMain
    SectionIn RO
    
    # Set output path
    SetOutPath "$INSTDIR"
    
    # Copy program files
    File /r "dist\FreePDF\*.*"
    
    # Create start menu items
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\FreePDF.lnk" "$INSTDIR\FreePDF.exe" "" "$INSTDIR\FreePDF.exe" 0
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\Uninstall FreePDF.lnk" "$INSTDIR\Uninstall.exe"
    
    # Create desktop shortcut
    CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\FreePDF.exe" "" "$INSTDIR\FreePDF.exe" 0
    
    # Registry entries
    WriteRegStr HKLM "Software\${APP_KEY}" "InstallPath" "$INSTDIR"
    WriteRegStr HKLM "Software\${APP_KEY}" "Version" "6.0.1"
    
    # Add to control panel programs list
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_KEY}" "DisplayName" "${APP_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_KEY}" "DisplayIcon" "$INSTDIR\FreePDF.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_KEY}" "Publisher" "FreePDF Team"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_KEY}" "DisplayVersion" "6.0.1"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_KEY}" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_KEY}" "NoRepair" 1
    
    # Calculate install size
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_KEY}" "EstimatedSize" "$0"
    
    # Create uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

# Uninstaller
Section "Uninstall"
    # Delete files
    RMDir /r "$INSTDIR"
    
    # Delete start menu items
    RMDir /r "$SMPROGRAMS\${APP_NAME}"
    
    # Delete desktop shortcut
    Delete "$DESKTOP\${APP_NAME}.lnk"
    
    # Delete registry entries
    DeleteRegKey HKLM "Software\${APP_KEY}"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_KEY}"
SectionEnd

# Pre-install check with improved update logic
Function .onInit
    # Check if already installed
    ReadRegStr $R0 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_KEY}" "UninstallString"
    ReadRegStr $R1 HKLM "Software\${APP_KEY}" "Version"
    
    StrCmp $R0 "" done
    
    # Check version for better update messaging
    StrCmp $R1 "6.0.1" same_version different_version
    
    same_version:
        MessageBox MB_OKCANCEL|MB_ICONQUESTION "FreePDF v6.0.1 is already installed.$\n$\nClick OK to reinstall or Cancel to exit." IDOK uninst
        Abort
        
    different_version:
        MessageBox MB_OKCANCEL|MB_ICONINFORMATION "FreePDF $R1 is installed.$\n$\nClick OK to upgrade to v6.0.1 or Cancel to exit." IDOK uninst
        Abort
    
    uninst:
        ClearErrors
        ExecWait '$R0 /S _?=$INSTDIR'
        
        IfErrors no_remove_uninstaller done
        IfFileExists "$INSTDIR\FreePDF.exe" no_remove_uninstaller done
        Delete $R0
        RMDir "$INSTDIR"
        
    no_remove_uninstaller:
    done:
FunctionEnd