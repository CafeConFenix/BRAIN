; BRAIN's graphical installer (Inno Setup 6). Compiled by CREAR_SETUP.bat; no need to open it by hand.
; Parameters: /DVersion=1.0.6  /DSource=<project folder>  /DPythonDir=<folder with portable Python>  /DOutput=<output folder>

#ifndef Version
  #define Version "0.0.0"
#endif
#ifndef Source
  #define Source ".."
#endif
#ifndef PythonDir
  #error Missing /DPythonDir (the folder with portable Python).
#endif
#ifndef Output
  #define Output ".."
#endif

[Setup]
AppId={{B7A1F3C2-6D54-4E0B-9A1E-5B1A4F0C8D21}
AppName=BRAIN
AppVersion={#Version}
AppVerName=BRAIN {#Version}
AppPublisher=BRAIN
DefaultDirName={localappdata}\BRAIN
DefaultGroupName=BRAIN
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir={#Output}
OutputBaseFilename=instalbrain ({#Version})
SetupIconFile={#Source}\brain\desktop\brain.ico
UninstallDisplayIcon={app}\brain\desktop\brain.ico
WizardStyle=modern
WizardImageFile={#Source}\instalador\imagenes\lateral.bmp
WizardSmallImageFile={#Source}\instalador\imagenes\pequena.bmp
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=no
RestartApplications=no
UsePreviousTasks=yes
ShowLanguageDialog=no
LanguageDetectionMethod=none

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Messages]
es.WelcomeLabel2=Este asistente instalara [name/ver] en tu ordenador.%n%nBRAIN es tu asistente personal para la casa: despensa, compra, gastos, energia y domotica. Todo funciona en tu propio ordenador.%n%nNo hace falta instalar nada mas: Python va incluido.
es.FinishedHeadingLabel=BRAIN esta listo
es.FinishedLabelNoIcons=La instalacion ha terminado.

[Tasks]
Name: "desktop"; Description: "Create a desktop icon"; GroupDescription: "Shortcuts:"
Name: "startup"; Description: "Open BRAIN when the computer starts (sits next to the clock)"; GroupDescription: "Options:"
Name: "ollama"; Description: "Install Ollama (needed for the artificial intelligence)"; GroupDescription: "Options:"; Check: not OllamaInstalled

[Files]
Source: "{#Source}\*"; DestDir: "{app}"; Excludes: "data\*,tests\*,docs\*,docker\*,.git\*,__pycache__\*,*.pyc,instalbrain*.exe,Setup.exe,python\*,instalador\imagenes\*,instalador\brain.iss,.pytest_cache\*"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#PythonDir}\*"; DestDir: "{app}\python"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\BRAIN"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\main.py"" --desktop"; WorkingDir: "{app}"; IconFilename: "{app}\brain\desktop\brain.ico"; Comment: "Open BRAIN"
Name: "{autodesktop}\BRAIN"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\main.py"" --desktop"; WorkingDir: "{app}"; IconFilename: "{app}\brain\desktop\brain.ico"; Tasks: desktop; Comment: "Open BRAIN"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "BRAIN"; ValueData: """{app}\python\pythonw.exe"" ""{app}\main.py"" --desktop --background"; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\instalador\preparar_ollama.ps1"""; StatusMsg: "Installing Ollama (the artificial intelligence). This can take a few minutes..."; Flags: runhidden waituntilterminated; Tasks: ollama
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\main.py"" --desktop"; WorkingDir: "{app}"; Description: "Open BRAIN now"; Flags: nowait postinstall skipifsilent

[Code]
function OllamaInstalled: Boolean;
begin
  Result := FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe'))
         or FileExists(ExpandConstant('{commonpf}\Ollama\ollama.exe'))
         or FileExists(ExpandConstant('{commonpf32}\Ollama\ollama.exe'));
end;

procedure CloseBrain(const Folder: String);
var
  Code: Integer;
  Python: String;
begin
  Python := Folder + '\python\pythonw.exe';
  if FileExists(Python) and FileExists(Folder + '\main.py') then
    Exec(Python, '"' + Folder + '\main.py" --close', Folder, SW_HIDE, ewWaitUntilTerminated, Code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  // If BRAIN was open (an update), it is closed so its files can be changed.
  CloseBrain(WizardDirValue);
  Sleep(1500);
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    CloseBrain(ExpandConstant('{app}'));
    Sleep(1500);

    if DirExists(ExpandConstant('{app}\data')) then
      if MsgBox('Do you also want to delete your data (pantry, shopping list, expenses, conversations and backups)?' + #13#10#13#10 +
                'If you say No, it is kept in case you install BRAIN again.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(ExpandConstant('{app}\data'), True, True, True);
  end;
end;
