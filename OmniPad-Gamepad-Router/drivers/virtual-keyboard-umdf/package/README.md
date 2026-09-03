# Bundled UMDF runtime package

This directory contains the minimal x64 runtime package produced from the adjacent OmniPad UMDF 2 source. It lets a supported Windows 11 host install the separate virtual keyboard without installing Visual Studio, WDK, SDK tools, or DevCon.

The package contains only:

- the UMDF driver DLL;
- its INF and signed catalog; and
- the public half of `CN=OmniPad Local UMDF Development`.

No private signing key is stored in this repository. `install-bundled-package.ps1` pins the SHA-256 hash of every artifact and the catalog signer thumbprint before asking Windows to trust or install it. Installation adds the public certificate only to the local machine Root and TrustedPublisher stores, and targets only `Root\OmniPadVirtualKeyboardUmdf`.

This is a private/development trust path, not a substitute for Microsoft/Partner Center signing. The separate KMDF/VHF source is preserved under `drivers/virtual-keyboard/` for that future route.
