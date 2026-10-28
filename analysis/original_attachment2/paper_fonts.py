"""Configure Chinese plotting font from local system; no font file is redistributed."""
import os
from pathlib import Path
from matplotlib import pyplot as plt,font_manager,ft2font
from matplotlib.text import Text
FACES={}
def configure(lang):
    fp=os.environ.get('LAZER_CJK_FONT','').strip()
    if not fp:
        for name in ('Noto Sans CJK SC','Noto Sans CJK JP','Source Han Sans SC','Microsoft YaHei','SimHei'):
            try:
                f=font_manager.findfont(font_manager.FontProperties(family=name),fallback_to_default=False)
                if Path(f).is_file():fp=f;break
            except Exception:pass
    if not fp or not Path(fp).is_file():
        raise RuntimeError('Chinese CJK font unavailable. Install Noto Sans CJK SC or set LAZER_CJK_FONT=/path/to/font.')
    face=ft2font.FT2Font(str(fp));font_manager.fontManager.addfont(str(fp))
    FACES[lang]=(face.family_name,set(face.get_charmap()))
    plt.rcParams.update({'font.family':face.family_name,'font.size':9,'axes.labelsize':10,'legend.fontsize':8,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'path','axes.unicode_minus':False,'savefig.bbox':'tight'})
def validate_text(fig,lang):
    chars={c for obj in fig.findobj(match=Text) for c in obj.get_text() if not c.isspace() and c not in '$^_{}' and c != chr(92)}
    missing=[c for c in chars if ord(c) not in FACES[lang][1]]
    if missing:raise RuntimeError('Chinese font missing characters: '+''.join(missing))
