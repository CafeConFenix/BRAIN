; Instalador grafico de BRAIN (Inno Setup 6). Lo compila CREAR_SETUP.bat; no hace falta abrirlo.
; Parametros: /DVersion=1.0.6  /DFuente=<carpeta del proyecto>  /DPythonDir=<carpeta con Python portable>  /DSalida=<carpeta de salida>

#ifndef Version
  #define Version "0.0.0"
#endif
#ifndef Fuente
  #define Fuente ".."
#endif
#ifndef PythonDir
  #error Falta /DPythonDir (la carpeta con Python portable).
#endif
#ifndef Salida
  #define Salida ".."
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
OutputDir={#Salida}
OutputBaseFilename=instalbrain ({#Version})
SetupIconFile={#Fuente}\brain\escritorio\brain.ico
UninstallDisplayIcon={app}\brain\escritorio\brain.ico
WizardStyle=modern
WizardImageFile={#Fuente}\instalador\imagenes\lateral.bmp
WizardSmallImageFile={#Fuente}\instalador\imagenes\pequena.bmp
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
Name: "escritorio"; Description: "Crear un icono en el escritorio"; GroupDescription: "Accesos directos:"
Name: "arranque"; Description: "Abrir BRAIN al encender el ordenador (queda junto al reloj)"; GroupDescription: "Opciones:"
Name: "ollama"; Description: "Instalar Ollama (necesario para la inteligencia artificial)"; GroupDescription: "Opciones:"; Check: not OllamaInstalado

[Files]
Source: "{#Fuente}\*"; DestDir: "{app}"; Excludes: "datos\*,tests\*,docs\*,docker\*,.git\*,__pycache__\*,*.pyc,instalbrain*.exe,Setup.exe,python\*,instalador\imagenes\*,instalador\brain.iss,.pytest_cache\*"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#PythonDir}\*"; DestDir: "{app}\python"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\BRAIN"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\main.py"" --escritorio"; WorkingDir: "{app}"; IconFilename: "{app}\brain\escritorio\brain.ico"; Comment: "Abrir BRAIN"
Name: "{autodesktop}\BRAIN"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\main.py"" --escritorio"; WorkingDir: "{app}"; IconFilename: "{app}\brain\escritorio\brain.ico"; Tasks: escritorio; Comment: "Abrir BRAIN"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "BRAIN"; ValueData: """{app}\python\pythonw.exe"" ""{app}\main.py"" --escritorio --segundo-plano"; Flags: uninsdeletevalue; Tasks: arranque

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\instalador\preparar_ollama.ps1"""; StatusMsg: "Instalando Ollama (la inteligencia artificial). Puede tardar unos minutos..."; Flags: runhidden waituntilterminated; Tasks: ollama
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\main.py"" --escritorio"; WorkingDir: "{app}"; Description: "Abrir BRAIN ahora"; Flags: nowait postinstall skipifsilent

[Code]
function OllamaInstalado: Boolean;
begin
  Result := FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe'))
         or FileExists(ExpandConstant('{commonpf}\Ollama\ollama.exe'))
         or FileExists(ExpandConstant('{commonpf32}\Ollama\ollama.exe'));
end;

procedure CerrarBrain(const Carpeta: String);
var
  Codigo: Integer;
  Python: String;
begin
  Python := Carpeta + '\python\pythonw.exe';
  if FileExists(Python) and FileExists(Carpeta + '\main.py') then
    Exec(Python, '"' + Carpeta + '\main.py" --cerrar', Carpeta, SW_HIDE, ewWaitUntilTerminated, Codigo);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  // Si BRAIN estaba abierto (actualizacion), se cierra para poder cambiar sus archivos.
  CerrarBrain(WizardDirValue);
  Sleep(1500);
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    CerrarBrain(ExpandConstant('{app}'));
    Sleep(1500);

    if DirExists(ExpandConstant('{app}\datos')) then
      if MsgBox('Quieres borrar tambien tus datos (despensa, lista de la compra, gastos, conversaciones y copias)?' + #13#10#13#10 +
                'Si dices que No, se conservan por si vuelves a instalar BRAIN.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(ExpandConstant('{app}\datos'), True, True, True);
  end;
end;
