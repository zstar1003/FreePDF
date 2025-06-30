# FreePDF Install Script
# Using NSIS (Nullsoft Scriptable Install System)

# Include Modern UI
!include "MUI2.nsh"
!include "FileFunc.nsh"

# Program Information
Name "FreePDF"
OutFile "FreePDF_Setup.exe"
InstallDir "$PROGRAMFILES64\FreePDF"
InstallDirRegKey HKLM "Software\FreePDF" "InstallPath"
RequestExecutionLevel admin

# Version Information
VIProductVersion "3.0.0.0"
VIAddVersionKey "ProductName" "FreePDF"
VIAddVersionKey "Comments" "Free PDF Translation Tool"
VIAddVersionKey "CompanyName" "FreePDF Team"
VIAddVersionKey "FileDescription" "FreePDF Setup"
VIAddVersionKey "FileVersion" "3.0.0.0"
VIAddVersionKey "ProductVersion" "3.0.0.0"
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
    CreateDirectory "$SMPROGRAMS\FreePDF"
    CreateShortCut "$SMPROGRAMS\FreePDF\FreePDF.lnk" "$INSTDIR\FreePDF.exe" "" "$INSTDIR\FreePDF.exe" 0
    CreateShortCut "$SMPROGRAMS\FreePDF\Uninstall FreePDF.lnk" "$INSTDIR\Uninstall.exe"
    
    # Create desktop shortcut
    CreateShortCut "$DESKTOP\FreePDF.lnk" "$INSTDIR\FreePDF.exe" "" "$INSTDIR\FreePDF.exe" 0
    
    # Registry entries
    WriteRegStr HKLM "Software\FreePDF" "InstallPath" "$INSTDIR"
    WriteRegStr HKLM "Software\FreePDF" "Version" "3.0.0"
    
    # Add to control panel programs list
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\FreePDF" "DisplayName" "FreePDF"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\FreePDF" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\FreePDF" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\FreePDF" "DisplayIcon" "$INSTDIR\FreePDF.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\FreePDF" "Publisher" "FreePDF Team"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\FreePDF" "DisplayVersion" "3.0.0"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\FreePDF" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\FreePDF" "NoRepair" 1
    
    # Calculate install size
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\FreePDF" "EstimatedSize" "$0"
    
    # Create uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

# Uninstaller
Section "Uninstall"
    # Delete files
    RMDir /r "$INSTDIR"
    
    # Delete start menu items
    RMDir /r "$SMPROGRAMS\FreePDF"
    
    # Delete desktop shortcut
    Delete "$DESKTOP\FreePDF.lnk"
    
    # Delete registry entries
    DeleteRegKey HKLM "Software\FreePDF"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\FreePDF"
SectionEnd

# Pre-install check with improved update logic
Function .onInit
    # Check if already installed
    ReadRegStr $R0 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\FreePDF" "UninstallString"
    ReadRegStr $R1 HKLM "Software\FreePDF" "Version"
    
    StrCmp $R0 "" done
    
    # Check version for better update messaging
    StrCmp $R1 "3.0.0" same_version different_version
    
    same_version:
        MessageBox MB_OKCANCEL|MB_ICONQUESTION "FreePDF v3.0.0 is already installed.$\n$\nClick OK to reinstall or Cancel to exit." IDOK uninst
        Abort
        
    different_version:
        MessageBox MB_OKCANCEL|MB_ICONINFORMATION "FreePDF $R1 is installed.$\n$\nClick OK to upgrade to v3.0.0 or Cancel to exit." IDOK uninst
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