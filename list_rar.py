import rarfile
import os

rar_files = [
    r'C:\Users\Lenovo\Downloads\D561EDF6847374AA20E92AF4991_D955CC9E_2E432.rar',
    r'C:\Users\Lenovo\Downloads\8DCFD1E648133808134CFD5410E_14C9F9A0_264BE.rar',
    r'C:\Users\Lenovo\Downloads\1B7B3931E5384423C7D714847E9_9271D219_A2ED.rar',
    r'C:\Users\Lenovo\Downloads\225BC03A0CAD180DCF42EFD4FAC_50FC4619_26B4D0.rar',
    r'C:\Users\Lenovo\Downloads\061AEDD5ECAFE8D3516A69EF6A5_AD87382D_2FDB.rar',
    r'C:\Users\Lenovo\Downloads\91DFB945E49E287954B6336364B_BFBDD629_1F02C8.rar',
    r'C:\Users\Lenovo\Downloads\F3CC906138A5511419E98B3F6E7_8FEE9441_5D3.rar',
    r'C:\Users\Lenovo\Downloads\685B0CA2F6EC1F0C9A428260A72_3A2AF387_FD66.rar',
]

for i, fpath in enumerate(rar_files, 1):
    fname = os.path.basename(fpath)
    try:
        rar = rarfile.RarFile(fpath)
        print(f"=== File {i}: {fname} ===")
        for info in rar.infolist():
            print(f"  {info.filename:60s} {info.file_size:>12,} bytes")
        print()
    except Exception as e:
        print(f"=== File {i}: {fname} - ERROR: {e} ===\n")
