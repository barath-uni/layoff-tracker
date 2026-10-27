"""Multilingual headline rules (non-English editions, GDELT, TDnet).

Same contract as extract.extract_headline: return {company, headcount, pct, kind, speculative, country, industry,
method, horizon} or None. Rule-based, per language:
  - a layoff keyword must be present (local wording),
  - company: a known name (gazetteer) in the headline, else "<layoff noun> at <Company>", else the capitalised
    subject in front of the verb (Latin, Cyrillic, Greek scripts), else the text before the particle/keyword (CJK),
  - headcount: a number next to a local job noun ("1.200 Stellen", "1 200 postes", "3 mil empleos", "2万人"),
  - the accuracy rules of the English parser carry over: rumour wording -> speculative, past totals -> no number,
    future multi-year targets -> kind "plan" (shown, never counted), protests -> no number, denials -> dropped.
Where regex is not enough (Thai, Arabic, Hebrew, Bengali company names) only the gazetteer finds the company;
research/notes.md records where the optional LLM hook (radar/llm.py, LR_LLM_CMD) would help.
"""
import re
import unicodedata

from .util import DATA

# ------------------------------------------------------------------ per-language tables
R = {}


def _rx(s):
    return re.compile(s, re.I) if s else None


def lang(code, kw, job, at=None, spec=None, past=None, plan=None, neg=None, roundup=None, mult=None, pctw=None,
         articles="", desc="", stop="", buyout=None):
    R[code] = {"kw": _rx(kw), "job": job, "at": at, "spec": _rx(spec), "past": _rx(past), "plan": _rx(plan),
               "neg": _rx(neg), "roundup": _rx(roundup), "mult": mult or {}, "pctw": pctw or "",
               "articles": set(articles.lower().split()), "desc": set(desc.lower().split()),
               "stop": set(stop.lower().split()), "buyout": _rx(buyout)}


PROTEST = _rx(r"protest|demonstr|manifest|kundgebung|mahnwache|grève|greve|huelga|sciopero|staking|strajk|strejk|streik|"
              r"rally|marcha|marche|presidio|protesta|протест|забастовк|eylem|grev|unjuk rasa|demo\b|"
              r"gegen (?:den |die )?(?:stellenabbau|entlassungen|kündigungen|jobabbau)|contre (?:les |la )?(?:licenciements|suppressions)|"
              r"contra (?:los |las |as |os )?(?:despidos|demissões|recortes)|contro (?:i |gli )?(?:licenziamenti|esuberi)|"
              r"tegen (?:de )?ontslagen|przeciw(?:ko)? zwolnieniom")
FUNCTION_WORDS = set("""bis nach vor wegen trotz auch jetzt nun wie warum was wer so mehr weitere neue neuer neues rund fast über etwa knapp
jeder erneut schon noch zudem dennoch kommentar analyse interview exklusiv eilmeldung update liveblog ticker
pourquoi comment après avant encore aussi désormais exclusif selon voici
por qué cómo tras antes también ahora además según exclusiva
por que como após depois também agora além segundo
perché come dopo prima anche ora ecco
waarom hoe na voor ook nu
dlaczego jak po przed także teraz
varför hur efter före också nu
""".split())

lang("de",
     kw=r"stellenabbau|entlass|stellen\s+(?:streich|abbau|weg)|streich\w*\s+(?:\S+\s+){0,3}(?:stellen|jobs|arbeitspl)|"
        r"baut\s+(?:\S+\s+){0,3}(?:stellen|jobs|arbeitspl\w+)\s+ab|abbau\s+von\s+(?:\S+\s+){0,2}(?:stellen|jobs|arbeitspl)|"
        r"jobabbau|arbeitsplatzabbau|kündigungswelle|kahlschlag|massenentlassung|personalabbau|sozialplan|"
        r"(?:stellen|jobs|arbeitsplätze)\s+(?:fallen\s+weg|wegfallen|gestrichen|abgebaut)",
     job=r"stellen|arbeitspl(?:ä|a)tze[n]?|jobs?|mitarbeite\w*|beschäftigte\w*|angestellte\w*|vollzeitstellen|personen|"
         r"menschen|leute|beschäftigungsverhältnisse|kündigungen|entlassungen|beschäftigten",
     at=r"(?:stellenabbau|entlassungen|jobabbau|kahlschlag|personalabbau|kündigungen|arbeitsplatzabbau|stellenstreichungen)"
        r"\s+(?:bei|beim|von|im\s+konzern)",
     spec=r"\bkönnte|\berwägt|\bprüft|\bdroh\w*|angeblich|bericht|offenbar|\bwohl\b|womöglich|insider|kreise[n]?\b|gerücht|"
          r"befürcht|\bfürcht|sorge um|nicht aus\b|nicht ausgeschlossen|\?|steht vor|wackel|zittern|bangen|gefährdet|auf der kippe|in gefahr|warnt",
     past=r"\bseit\s+20\d\d|\bbisher\b|insgesamt|in den letzten|im vergangenen jahr|letztes jahr|seit jahresbeginn|bereits\s+\d|"
          r"im jahr 20\d\d|vergangenen jahren",
     plan=r"\bbis\s+(?:ende\s+|zum\s+jahr\s+|zum\s+ende\s+)?(20\d\d)|in den (?:nächsten|kommenden) (?:\w+ )?jahren|bis ende des jahrzehnts|mittelfristig",
     neg=r"keine entlassungen|kein stellenabbau|ohne (?:stellenabbau|entlassungen)|verzicht\w* auf|stellt\s+(?:\S+\s+)?ein\b|"
         r"neueinstellung|einstellungsstopp|klage|klagt|gericht|urteil|zurückgenommen|abgewendet",
     roundup=r"diese (?:firmen|unternehmen|konzerne)|liste|überblick|welle\b|immer mehr|reihenweise|branchen\b|ticker",
     mult={"tausend": 1000, "tsd": 1000, "mio": 1_000_000, "millionen": 1_000_000},
     pctw=r"belegschaft|mitarbeite\w*|stellen|beschäftigte\w*|personal\w*|arbeitspl\w+",
     articles="der die das den dem des ein eine einer einem",
     desc="autobauer autozulieferer zulieferer konzern chipkonzern chemiekonzern softwarekonzern techkonzern pharmakonzern "
          "industriekonzern energiekonzern handelskonzern medienkonzern stahlkonzern elektronikkonzern logistikkonzern "
          "hersteller maschinenbauer anlagenbauer händler modehändler onlinehändler einzelhändler versandhändler "
          "versicherer bankhaus geldhaus unternehmen firma gruppe tochter mutterkonzern dienstleister anbieter betreiber "
          "riese gigant start-up startup traditionsunternehmen familienunternehmen mittelständler discounter "
          "kette lebensmittelhändler drogeriekette warenhauskette baumarktkette tech-riese autoriese verlag zeitung "
          "fluggesellschaft airline reederei stahlhersteller chiphersteller automobilzulieferer elektroautobauer "
          "medizintechnikhersteller pharmaunternehmen rüstungskonzern energieversorger versorger stadtwerke standort werk "
          "pharmastandort us-konzern us-techkonzern us-autobauer softwarehersteller hausgerätehersteller",
     stop="stellenabbau entlassungen jobabbau beschäftigte mitarbeiter mitarbeitende tausende hunderte industrie autoindustrie "
          "wirtschaft deutschland regierung bundesregierung land stadt gewerkschaft betriebsrat ig metall verdi chef ceo "
          "kahlschlag krise sparkurs sparprogramm umbau konzernumbau arbeitsplätze jobs stellen unternehmen konzerne firmen "
          "branche autobranche zulieferer autozulieferer hersteller banken experten studie umfrage bericht neue weitere "
          "massiver drastischer großer weiterer nach wegen trotz nach dem vor kurz exklusiv eilmeldung liveticker news "
          "aktie aktien börse dax mdax sdax quartal halbjahr gewinn umsatz verlust milliarden millionen prozent euro "
          "standort werk werke fabrik betrieb sozialplan kündigungen kündigungswelle angst sorge wut protest streik "
          "europa europas deutschlands bayern baden-württemberg niedersachsen nrw sachsen hessen berlin hamburg "
          "maschinenbau chemie chemieindustrie stahlindustrie metall- metallindustrie elektroindustrie pharma deutsche "
          "beschäftigung arbeitsmarkt jobmarkt ki künstliche intelligenz automatisierung mittelstand handel einzelhandel "
          "bundesagentur arbeitsagentur ifo diw iab statistik kurzarbeit insolvenz pleite")

lang("fr",
     kw=r"licenci|suppressions?\s+(?:de\s+)?(?:\d[\d\s.]*\s+)?(?:postes|emplois)|supprim\w*\s+(?:\S+\s+){0,3}(?:postes|emplois)|"
        r"plan social|plan de sauvegarde de l'emploi|\bpse\b|plan de départs|réduction (?:des|d')\s*effectifs|"
        r"suppression d'emplois|coupes? dans les effectifs|vague de départs",
     job=r"postes|emplois|salariés|employés|personnes|licenciements|suppressions|collaborateurs|agents|cdi|personnels?",
     at=r"(?:licenciements|suppressions de postes|plan social|pse|plan de départs|suppressions d'emplois|coupes)\s+(?:chez|à|au sein de|de|d')",
     spec=r"pourrait|envisag|\bselon\b|menac|rumeur|craint|craintes|serait|seraient|\?|inquiét|risque|redout|en sursis",
     past=r"\bdepuis\b|au total|en tout|l'an dernier|l'année dernière|\ben 20\d\d|\bdéjà\b",
     plan=r"d'ici (?:à |la fin |fin )?(?:de )?(20\d\d)|d'ici (?:à )?\d+ ans|dans les (?:\w+ )?prochaines années|à l'horizon (20\d\d)",
     neg=r"pas de licenciement|aucun licenciement|sans licenciement|recrut|embauch|tribunal|justice|annul|prud'?hom|suspendu",
     roundup=r"ces entreprises|la liste|vague de|les entreprises qui|en série|cascade",
     mult={"mille": 1000, "millions": 1_000_000},
     pctw=r"effectifs?|salariés|personnel|employés|postes|main-d'œuvre",
     articles="le la les l' l’ un une des du de d' d’",
     desc="constructeur équipementier groupe géant fabricant distributeur enseigne entreprise société firme opérateur "
          "spécialiste leader numéro chimiste sidérurgiste assureur banque laboratoire éditeur fournisseur sous-traitant "
          "américain allemand français britannique japonais chinois suisse italien belge",
     stop="licenciements emplois postes salariés france gouvernement syndicats syndicat cgt cfdt fo état etat entreprises "
          "industrie automobile secteur plan social pse grève usine site usines sites ministre ministère bercy paris "
          "europe l'europe ia intelligence artificielle chômage emploi chômeurs nouveau nouvelle nouvelles nouveaux vague "
          "après avant pourquoi comment exclusif info alerte direct vidéo")

lang("es",
     kw=r"despid|\bere\b|\berte\b|recorte\w*\s+de\s+(?:\S+\s+){0,2}(?:empleos|personal|plantilla|puestos|trabajadores)|"
        r"despido masivo|reducción de (?:plantilla|personal)|elimina\w*\s+(?:\S+\s+){0,3}(?:empleos|puestos)|"
        r"suprim\w*\s+(?:\S+\s+){0,3}(?:empleos|puestos)|recort\w*\s+(?:\S+\s+){0,3}(?:empleos|puestos|trabajadores)|"
        r"cesantías|desvincula",
     job=r"empleos|empleados|trabajadores|puestos|personas|despidos|plazas|colaboradores|empleadas|trabajadoras",
     at=r"(?:despidos|ere|erte|recortes|despido masivo|despido colectivo)\s+(?:en|de)",
     spec=r"podría|estudia|plantea|\bsegún\b|amenaz|rumor|teme|temen|baraja|analiza|\?|en riesgo|peligro|prevé|preocupación|incertidumbre",
     past=r"\bdesde\b|en total|el año pasado|\ben 20\d\d|\bya\b|en lo que va",
     plan=r"(?:hasta|para|antes de)\s+(?:finales\s+de\s+|el\s+)?(20\d\d)|en los próximos (?:\w+ )?años",
     neg=r"sin despidos|no habrá despidos|descarta|contrat|tribunal|juez|anula|readmi|improceden|nulo",
     roundup=r"estas empresas|lista|ola de|las empresas que|oleada",
     mult={"mil": 1000, "millones": 1_000_000},
     pctw=r"plantilla|personal|empleados|trabajadores|fuerza laboral",
     articles="el la los las un una del de",
     desc="fabricante grupo gigante empresa compañía firma operadora tecnológica multinacional cadena aseguradora "
          "banco entidad automotriz constructora minera petrolera aerolínea",
     stop="despidos ere erte empleo trabajadores gobierno sindicatos sindicato ccoo ugt españa méxico argentina chile colombia "
          "perú empresas sector industria crisis huelga ministerio trabajo plantilla nuevo nueva nuevos ola ia economía")

lang("pt",
     kw=r"demiss|demit\w*|despedimento|despede|corte\w*\s+de\s+(?:\S+\s+){0,2}(?:empregos|vagas|funcionários|postos)|"
        r"\blayoff\b|redução de (?:quadro|pessoal|funcionários)|elimina\w*\s+(?:\S+\s+){0,3}(?:vagas|empregos|postos)|"
        r"desligamentos?|pdv\b",
     job=r"empregos|funcionários|trabalhadores|vagas|postos|pessoas|demissões|colaboradores|empregados|despedimentos|"
         r"profissionais|servidores",
     at=r"(?:demissões|despedimentos|layoff|cortes|demissão em massa|desligamentos)\s+(?:na|no|da|do|em)",
     spec=r"poderá|\bpode\b|estuda|avalia|\bsegundo\b|ameaç|rumor|teme|risco|\?|prevê|possível",
     past=r"\bdesde\b|no total|ano passado|\bem 20\d\d|\bjá\b",
     plan=r"\baté\s+(?:o\s+fim\s+de\s+|20)?(20\d\d|\d\d)\b|nos próximos (?:\w+ )?anos",
     neg=r"sem demissões|\bnão\b(?:\s+\S+){0,3}\s+(?:demitiu|demite|fechou)|desmente|\bnega\b|descarta|contrat|greve|justiça|tribunal|reintegr|suspende",
     roundup=r"essas empresas|lista|onda de|as empresas que|empresas que",
     mult={"mil": 1000, "milhões": 1_000_000},
     pctw=r"funcionários|quadro|força de trabalho|empregados|colaboradores|pessoal",
     articles="o a os as um uma da do de",
     desc="montadora fabricante grupo gigante empresa companhia gigante varejista operadora startup banco "
          "seguradora mineradora petroleira companhia aérea rede",
     stop="demissões empregos trabalhadores governo sindicatos sindicato brasil portugal empresas setor indústria crise greve "
          "ministério trabalho nova novo novas onda ia economia mercado")

lang("it",
     kw=r"licenzia|esuber|tagli\w*\s+(?:di\s+|dei\s+|al\s+|ai\s+)?(?:\S+\s+){0,2}(?:posti|personale|dipendenti|lavoratori)|"
        r"taglia\s+(?:\S+\s+){0,3}(?:posti|dipendenti|lavoratori)|riduzione del personale|cassa integrazione a zero|"
        r"uscite volontarie|mobilità",
     job=r"posti(?: di lavoro)?|dipendenti|lavoratori|esuberi|licenziamenti|persone|addetti|impiegati|tagli",
     at=r"(?:licenziamenti|esuberi|tagli)\s+(?:alla|all'|in|da|presso|nella|nel|per)",
     spec=r"potrebbe|valuta|\bsecondo\b|rischi|minacc|timor|teme|ipotesi|\?|rumors?|incertezza|in bilico",
     past=r"\bdal 20\d\d|in totale|l'anno scorso|nel 20\d\d|\bgià\b|finora",
     plan=r"entro (?:il |la fine del )?(20\d\d)|nei prossimi (?:\w+ )?anni",
     neg=r"nessun licenziamento|senza licenziamenti|esclude|assum|assunzioni|sciopero|tribunale|reintegr|ritirat|sospes",
     roundup=r"ecco le aziende|elenco|ondata|le aziende che",
     mult={"mila": 1000, "milioni": 1_000_000},
     pctw=r"personale|dipendenti|forza lavoro|organico",
     articles="il lo la i gli le un una l' dell' della del",
     desc="colosso gruppo azienda società produttore casa costruttore big gigante multinazionale",
     stop="licenziamenti esuberi lavoratori governo sindacati sindacato cgil cisl uil italia aziende settore industria crisi "
          "sciopero ministero lavoro tagli nuovi nuove ondata ia mimit regione")

lang("nl",
     kw=r"ontsla|banen\s+(?:weg|verdwijnen|schrappen)|schrap\w*\s+(?:\S+\s+){0,3}(?:banen|arbeidsplaatsen|functies|fte)|"
        r"(?:banen|arbeidsplaatsen|functies)\s+(?:op de tocht|verdwijnen|weg)|reorganisatie|ontslaggolf|massaontslag|"
        r"\bschrapt\b|banenverlies|herstructurering",
     job=r"banen|werknemers|medewerkers|arbeidsplaatsen|ontslagen|mensen|personeelsleden|fte|voltijdsbanen|functies|jobs",
     at=r"(?:ontslagen|banenverlies|reorganisatie|ontslaggolf|massaontslag|herstructurering)\s+(?:bij|in)",
     spec=r"overweegt|mogelijk|\bzou\b|dreig|\bvolgens\b|bronnen|vrees|\?|onzeker",
     past=r"\bsinds\b|in totaal|vorig jaar|\bin 20\d\d",
     plan=r"\b(?:tegen|voor|tot)\s+(?:eind\s+)?(20\d\d)|in de komende (?:\w+ )?jaren",
     neg=r"geen ontslagen|zonder ontslagen|sluit uit|neemt aan|vacatures|staking|rechter|geschrapt plan",
     roundup=r"deze bedrijven|lijst|golf\b|bedrijven die",
     mult={"duizend": 1000, "miljoen": 1_000_000},
     pctw=r"personeel|medewerkers|werknemers|banen|personeelsbestand",
     articles="de het een",
     desc="chipmachinemaker chipfabrikant concern bedrijf fabrikant techbedrijf bank verzekeraar winkelketen keten "
          "supermarktketen maker producent groep",
     stop="ontslagen banen werknemers kabinet regering vakbond fnv cnv nederland belgië vlaanderen bedrijven sector industrie "
          "reorganisatie staking minister nieuwe golf ai")

lang("pl",
     kw=r"zwolni|redukcj\w*\s+(?:\S+\s+){0,2}(?:etatów|zatrudnienia|miejsc)|likwidacj\w*\s+(?:\S+\s+){0,2}(?:etatów|miejsc pracy)|"
        r"zwolnienia grupowe|tnie etaty|cięcia etatów",
     job=r"pracownik\w*|osób|osoby|etatów|etaty|miejsc pracy|zwolnień|ludzi",
     at=r"(?:zwolnienia(?: grupowe)?|redukcja etatów|cięcia)\s+(?:w|we)",
     spec=r"\bmoże\b|\bmogą\b|rozważa|\bwedług\b|groź|\?|nieoficjalnie|plotk|obaw",
     past=r"\bod 20\d\d|łącznie|w ubiegłym roku|w 20\d\d|\bjuż\b",
     plan=r"\bdo\s+(?:końca\s+)?(20\d\d)|w ciągu (?:\w+ )?lat",
     neg=r"bez zwolnień|nie będzie zwolnień|zatrudni|rekrut|strajk|sąd",
     roundup=r"te firmy|lista|fala\b|firmy, które",
     mult={"tys": 1000, "tysięcy": 1000},
     pctw=r"załogi|pracowników|zatrudnienia|kadry",
     desc="koncern producent firma spółka gigant grupa bank sieć operator",
     stop="zwolnienia pracownicy rząd związki polska firmy branża przemysł strajk ministerstwo nowe fala")

lang("sv",
     kw=r"varsla|varsel|säger upp|uppsägning|skär ner|minskar (?:\S+\s+){0,2}(?:personal|anställda|tjänster)|"
        r"(?:tjänster|jobb)\s+försvinner|neddragning",
     job=r"anställda|jobb|tjänster|personer|medarbetare|varsel|varslas|varslade|heltidstjänster|uppsägningar",
     at=r"(?:varsel|uppsägningar|neddragningar)\s+(?:på|hos|inom|vid)",
     spec=r"\bkan\b|överväger|\benligt\b|hota|uppgifter|\?|risk",
     past=r"\bsedan\b|totalt|förra året|\bi 20\d\d|\bredan\b",
     plan=r"\b(?:till|före|innan)\s+(?:slutet av\s+)?(20\d\d)|inom (?:\w+ )?år|de närmaste (?:\w+ )?åren",
     neg=r"inga uppsägningar|anställer|rekryter|strejk|domstol",
     roundup=r"de här företagen|lista|våg\b",
     mult={"tusen": 1000},
     pctw=r"personal|anställda|arbetsstyrkan|medarbetare",
     desc="koncernen bolaget företaget tillverkaren jätten banken",
     stop="varsel uppsägningar regeringen facket sverige företag industrin strejk nya")

lang("no",
     kw=r"nedbemann|oppsigelse|sier opp|kutter\s+(?:\S+\s+){0,2}(?:stillinger|årsverk|ansatte|jobber)|permitter|"
        r"(?:stillinger|årsverk)\s+forsvinner",
     job=r"ansatte|stillinger|jobber|årsverk|personer|medarbeidere|oppsigelser",
     at=r"(?:nedbemanning|oppsigelser|kutt)\s+(?:i|hos|på)",
     spec=r"\bkan\b|vurderer|\bifølge\b|true|\?|mulig",
     past=r"\bsiden\b|totalt|i fjor|\bi 20\d\d",
     plan=r"\b(?:innen|frem mot|til)\s+(20\d\d)|de neste (?:\w+ )?årene",
     neg=r"ingen oppsigelser|ansetter|streik|retten",
     mult={"tusen": 1000},
     pctw=r"ansatte|arbeidsstokken|bemanningen",
     stop="nedbemanning oppsigelser regjeringen norge bedrifter streik nye")

lang("da",
     kw=r"fyring|fyrer|afskedig|nedlægger\s+(?:\S+\s+){0,2}(?:stillinger|job)|skærer\s+(?:\S+\s+){0,3}(?:stillinger|job|medarbejdere)|"
        r"sparerunde|(?:stillinger|job)\s+forsvinder",
     job=r"ansatte|stillinger|job|medarbejdere|personer|fyringer|årsværk",
     at=r"(?:fyringer|afskedigelser|sparerunde)\s+(?:i|hos|på)",
     spec=r"\bkan\b|overvejer|\bifølge\b|trues|truer|\?|mulig",
     past=r"\bsiden\b|i alt|sidste år|\bi 20\d\d",
     plan=r"\b(?:inden|frem mod|til)\s+(20\d\d)|de kommende (?:\w+ )?år",
     neg=r"ingen fyringer|ansætter|strejke|retten",
     mult={"tusind": 1000},
     pctw=r"medarbejdere|ansatte|arbejdsstyrken",
     stop="fyringer regeringen danmark virksomheder strejke nye")

lang("fi",
     kw=r"irtisano|muutosneuvottelu|yt-neuvottelu|vähentää\s+(?:\S+\s+){0,2}(?:työpaikkaa|henkilöä|työntekijää)|lomautt",
     job=r"työntekijää|henkilöä|työpaikkaa|irtisanomista|henkeä|työntekijän|hengen|henkilön",
     spec=r"\bvoi\b|harkitsee|saattaa|uhka|\?|mukaan",
     past=r"\bvuodesta\b|yhteensä|viime vuonna",
     plan=r"vuoteen (20\d\d) mennessä",
     neg=r"ei irtisanomisia|palkkaa|rekrytoi|lakko|oikeus",
     pctw=r"henkilöstö\w*|työntekijöistä",
     stop="irtisanomiset muutosneuvottelut hallitus suomi yritykset lakko")

lang("cs", kw=r"propouš|propust|hromadné propouštění|zruší\s+(?:\S+\s+){0,2}míst|rušení míst|škrty",
     job=r"zaměstnanc\w*|lidí|pracovních míst|pracovník\w*|míst|lidi",
     spec=r"\bmůže\b|zvažuje|\bpodle\b|hrozí|\?", past=r"\bod roku\b|celkem|loni", plan=r"\bdo\s+(?:roku\s+)?(20\d\d)",
     neg=r"bez propouštění|nabírá|stávka|soud", pctw=r"zaměstnanců|pracovníků", stop="propouštění vláda česko firmy stávka")
lang("hu", kw=r"leépít|elbocsát|kirúg|munkahely\w* szűn", job=r"dolgozó\w*|munkahely\w*|ember\w*|munkavállaló\w*|főt\b|fő\b",
     spec=r"\blehet\b|fontolgat|szerint|\?", past=r"tavaly|összesen", plan=r"(20\d\d)-ig", neg=r"nincs leépítés|felvesz|sztrájk|bíróság",
     pctw=r"dolgozó\w*|munkavállaló\w*", stop="leépítés elbocsátás kormány magyarország cégek")
lang("ro", kw=r"concedi|disponibiliz|reduce\w*\s+(?:\S+\s+){0,2}(?:posturi|personal)|desființ\w*\s+(?:\S+\s+){0,2}posturi",
     job=r"angajați|angajaţi|locuri de muncă|salariați|oameni|persoane|posturi|angajaților", spec=r"\bar putea\b|analizează|\bpotrivit\b|\?",
     past=r"\bdin 20\d\d|în total|anul trecut", plan=r"până în (20\d\d)", neg=r"fără concedieri|angajează|grevă|instanț",
     mult={"mii": 1000}, pctw=r"angajați|personal", stop="concedieri guvernul românia firme grevă")
lang("el", kw=r"απολύσ|περικοπ\w* θέσεων|καταργ\w* θέσ", job=r"εργαζόμεν\w*|θέσεις|υπαλλήλ\w*|απολύσεις|άτομα",
     spec=r"ενδέχεται|εξετάζει|σύμφωνα|\?", past=r"πέρυσι|συνολικά", neg=r"χωρίς απολύσεις|προσλήψεις|απεργία",
     stop="απολύσεις κυβέρνηση ελλάδα")
lang("tr", kw=r"işten çıkar|işçi çıkar|personel çıkar|çalışan\w* çıkar|toplu çıkış|kadro\w* daralt|istihdam\w* azalt",
     job=r"çalışan\w*|işçi\w*|personel\w*|kişi\w*|kişiyi", spec=r"iddia|olabilir|gündem|\?|kulis|hazırlanıyor|söylenti",
     past=r"\bgeçen yıl|toplamda|20\d\d'de|20\d\d yılında", plan=r"(20\d\d)'?(?:e|a|ye|ya) kadar",
     neg=r"işten çıkarma yok|işe alım|alım yapacak|grev|mahkeme", mult={"bin": 1000},
     pctw=r"çalışan\w*|personel\w*|işgücü\w*", stop="işten çıkarma işçiler hükümet türkiye şirketler sektör grev yeni")
lang("ru", kw=r"сокра[щт]|уволь|увольн|массов\w* сокращ|оптимизац\w* (?:штата|персонала)",
     job=r"сотрудник\w*|работник\w*|человек|рабочих|мест\w*|вакансий|специалист\w*|служащих",
     at=r"(?:сокращения|увольнения|сокращение)\s+(?:в|во|на)",
     spec=r"может|могут|рассматрива|сообща\w*|источник|слух|\?|возможн|планирует ли",
     past=r"\bс 20\d\d|в прошлом году|всего\b|за год|в 20\d\d году", plan=r"\bдо\s+(?:конца\s+)?(20\d\d)\s+год",
     neg=r"не будет сокращ|не планирует|набира|наним|суд|забастовк", mult={"тыс": 1000, "тысяч": 1000, "тысячи": 1000},
     pctw=r"сотрудник\w*|персонал\w*|штат\w*|работник\w*", stop="сокращения увольнения правительство россия компании минтруд")
lang("uk", kw=r"скороч|звільн|масов\w* звільн|оптимізац\w* штату", job=r"працівник\w*|співробітник\w*|людей|осіб|місць|робочих",
     at=r"(?:скорочення|звільнення)\s+(?:в|у|на)", spec=r"може|можуть|розглядає|джерел|\?", past=r"минулого року|загалом|з 20\d\d",
     plan=r"до\s+(20\d\d)\s+рок", neg=r"без звільнень|набира|суд", mult={"тис": 1000, "тисяч": 1000},
     pctw=r"працівник\w*|персонал\w*|штат\w*", stop="скорочення звільнення уряд україна компанії")
lang("id", kw=r"\bphk\b|pemutusan hubungan kerja|merumahkan|pengurangan (?:karyawan|pegawai|pekerja)|pangkas\w*\s+(?:\S+\s+){0,2}(?:karyawan|pegawai)",
     job=r"karyawan|pekerja|buruh|pegawai|orang|staf|tenaga kerja", at=r"(?:phk|pemutusan hubungan kerja|pengurangan karyawan)\s+(?:di|karyawan)",
     spec=r"kabarnya|dikabarkan|\bbisa\b|berpotensi|terancam|\bisu\b|\?|kemungkinan|bakal",
     past=r"\bsejak\b|sepanjang|total|tahun lalu|selama 20\d\d", plan=r"(?:hingga|sampai)\s+(20\d\d)",
     neg=r"tidak ada phk|tak ada phk|bantah|membantah|rekrut|lowongan|mogok|pengadilan|gugat", mult={"ribu": 1000, "rb": 1000},
     pctw=r"karyawan|pegawai|pekerja", articles="pt",
     stop="phk karyawan pekerja buruh pemerintah kemnaker menaker indonesia perusahaan pabrik industri sektor ribuan ratusan "
          "gelombang marak badai kasus jumlah data apindo")
lang("ms", kw=r"pemberhentian|buang kerja|diberhentikan|vss\b|vsss?\b", job=r"pekerja|kakitangan|orang", spec=r"mungkin|dikatakan|\?",
     stop="pekerja kerajaan malaysia syarikat")
lang("vi", kw=r"sa thải|cắt giảm (?:\S+\s+){0,2}(?:nhân sự|nhân viên|lao động|việc làm)|cho nghỉ việc|giảm biên chế",
     job=r"nhân viên|lao động|người|công nhân|việc làm|nhân sự", spec=r"có thể|tin đồn|\?|nguy cơ|dự kiến",
     past=r"năm ngoái|tổng cộng|từ năm 20\d\d", plan=r"đến năm (20\d\d)", neg=r"không sa thải|tuyển dụng|đình công|tòa án",
     mult={"nghìn": 1000, "ngàn": 1000}, pctw=r"nhân viên|nhân sự|lao động",
     stop="sa thải lao động chính phủ việt nam doanh nghiệp công ty làn sóng hàng loạt")
lang("ja", kw=r"人員削減|希望退職|早期退職|リストラ|解雇|人員整理|削減.{0,6}(?:人|名)|(?:人|名).{0,4}削減|雇い止め|工場閉鎖|"
               r"拠点閉鎖|退職者.{0,4}募集", job="", spec=r"検討|方針|調整|観測|報道|か$|か[\s　|｜]|も$|恐れ|可能性|浮上|へ調整",
     past=r"累計|これまで|昨年|前年|上半期|1-9月|1～9月", plan=r"(20\d\d)年(?:度)?(?:まで|末まで)|(\d+)年(?:間)?で",
     neg=r"採用|撤回|否定|雇用維持|雇用を守", roundup=r"まとめ|一覧|相次ぐ|続々|企業[数は]|社に|社で|上場企業|何社")
lang("zh", kw=r"裁员|裁員|人员优化|大裁员|优化\d|毕业|裁撤|减员|減員|关闭工厂|關閉工廠|解雇|遣散", job="",
     spec=r"传|傳|曝|据悉|據悉|或将|或將|可能|消息称|消息稱|网传|網傳|传闻|傳聞|考虑|考慮|[?？]|疑似|否认|否認",
     past=r"累计|累計|此前|去年|今年以来|今年以來|迄今|已裁", plan=r"到(20\d\d)年|(20\d\d)年前|未来\w*年",
     neg=r"辟谣|闢謠|招聘|扩招|擴招|不裁员|不裁員|否认裁员|否認裁員|仲裁",
     roundup=r"盘点|盤點|汇总|匯總|多家|一览|一覽|潮$|潮[，,]|大厂们|們")
lang("ko", kw=r"구조조정|희망퇴직|감원|정리해고|인력 감축|인원 감축|해고|명예퇴직|권고사직", job="",
     spec=r"검토|가능성|전망|관측|설\b|우려|[?？]|추진하나", past=r"누적|지난해|올해 들어|그동안", plan=r"(20\d\d)년까지",
     neg=r"채용|부인|없다|철회", roundup=r"줄줄이|잇따라|잇단|업계 전반")
lang("hi", kw=r"छंटनी|छँटनी|नौकरी से निकाल|नौकरियां? (?:खत्म|गईं)|बर्खास्त|ले-?ऑफ|लेऑफ", job=r"कर्मचारि\w*|लोगों|नौकरि\w*|कर्मी\w*|employees",
     spec=r"सकती|सकता|संभव|खबर|रिपोर्ट|\?", past=r"पिछले साल|अब तक|कुल", plan=r"(20\d\d) तक", neg=r"भर्ती|नहीं होगी छंटनी",
     mult={"हजार": 1000, "हज़ार": 1000, "लाख": 100_000})
lang("bn", kw=r"ছাঁটাই|চাকরিচ্যুত", job=r"কর্মী\w*|জন", spec=r"\?", mult={"হাজার": 1000})
lang("th", kw=r"เลิกจ้าง|ปลดพนักงาน|ปลดคน|ลดพนักงาน", job=r"พนักงาน|คน|ราย", spec=r"พิจารณา|อาจ|\?", mult={"พัน": 1000})
lang("ar", kw=r"تسريح|الاستغناء عن|فصل\s+\S*\s*(?:موظف|عامل)|خفض\s+\S*\s*(?:الوظائف|العمالة)", job=r"موظف\w*|عامل\w*|وظيفة|وظائف",
     spec=r"قد\b|يدرس|\?|؟", mult={"ألف": 1000, "آلاف": 1000})
lang("he", kw=r"פיטור|מפטר|קיצוץ\s+\S*\s*(?:עובדים|משרות)|צמצום", job=r"עובדים|משרות|עובד", spec=r"עשוי|שוקל|\?", mult={"אלף": 1000})

STOP_ALL = set("""ai ia ki it ceo cfo eu ue usa us abd ии ші ит hr pr hlv belgische deense duitse franse amerikaanse britse
nederlandse britisk tre lokale färre arbetslösheten známá όχι τι οι να δεν folytatódik óriási kevesebb újabb tömeges
ultima oră ultima ora orang kena kemnaker kemnaker catat cơn заява виїзд змушують krakowie warszawie
korban sebanyak lebih tekstil es wo ur state kalsel jatim jateng jabar jakarta angka dona eeuu ee.uu milei naver pt ms rs n.j""".split()) | {
    "ultima oră", "orang kena", "kemnaker catat", "у росії", "в россии"}
# A name containing any of these words is wording, not an employer ("50 Ribu Pekerja Terdampak PHK", "BMW Pracę").
REJECT_TOKENS = set("""ribu pekerja kemnaker korban sebanyak pelatihan terdampak kena tenaga disnaker disnakertrans pemprov
pracę eeuu ee.uu dione""".split())
# Lower-case word counts per language, filled by consensus.build_claims from the corpus itself.
VOCAB = {}


def learn_vocab(title, code):
    if code in LATIN:
        v = VOCAB.setdefault(code, {})
        for w in re.findall(r"[^\W\d_][\w'’-]*", title):
            if w[0].islower():
                v[w] = v.get(w, 0) + 1


LATIN = {"de", "fr", "es", "pt", "it", "nl", "pl", "sv", "no", "da", "fi", "cs", "hu", "ro", "el", "tr", "ru", "uk", "id", "ms", "vi"}
CJK = {"ja", "zh", "ko"}

# Common names in local scripts -> display name (the gazetteer then maps it to the canonical slug).
SCRIPT_NAMES = {
    "巴克莱": "Barclays", "巴克萊": "Barclays", "巴克莱银行": "Barclays", "巴克萊銀行": "Barclays", "바클레": "Barclays",
    "바클레이스": "Barclays", "우버": "Uber", "优步": "Uber", "優步": "Uber", "运通": "American Express", "運通": "American Express", "볼보": "Volvo",
    "奈飞": "Netflix", "網飛": "Netflix", "애플": "Apple", "保时捷": "Porsche", "保時捷": "Porsche", "포르쉐": "Porsche",
    "マイクロソフト": "Microsoft", "アマゾン": "Amazon", "グーグル": "Google", "メタ": "Meta", "アップル": "Apple",
    "インテル": "Intel", "オラクル": "Oracle", "テスラ": "Tesla", "日産": "Nissan", "日産自動車": "Nissan",
    "トヨタ": "Toyota", "トヨタ自動車": "Toyota", "ホンダ": "Honda", "本田技研工業": "Honda", "パナソニック": "Panasonic",
    "ソニー": "Sony", "東芝": "Toshiba", "日立": "Hitachi", "日立製作所": "Hitachi", "富士通": "Fujitsu", "NEC": "NEC",
    "三菱自動車": "Mitsubishi Motors", "マツダ": "Mazda", "シャープ": "Sharp", "ジャパンディスプレイ": "Japan Display",
    "楽天": "Rakuten", "資生堂": "Shiseido", "オムロン": "Omron", "コニカミノルタ": "Konica Minolta",
    "微软": "Microsoft", "微軟": "Microsoft", "亚马逊": "Amazon", "亞馬遜": "Amazon", "谷歌": "Google", "英特尔": "Intel",
    "英特爾": "Intel", "特斯拉": "Tesla", "甲骨文": "Oracle", "苹果": "Apple", "蘋果": "Apple", "字节跳动": "ByteDance",
    "字節跳動": "ByteDance", "阿里巴巴": "Alibaba", "阿里": "Alibaba", "腾讯": "Tencent", "騰訊": "Tencent", "百度": "Baidu",
    "京东": "JD.com", "京東": "JD.com", "小米": "Xiaomi", "华为": "Huawei", "華為": "Huawei", "比亚迪": "BYD", "比亞迪": "BYD",
    "蔚来": "NIO", "小鹏": "XPeng", "理想汽车": "Li Auto", "美团": "Meituan", "美團": "Meituan", "拼多多": "PDD",
    "网易": "NetEase", "網易": "NetEase", "快手": "Kuaishou", "联想": "Lenovo", "聯想": "Lenovo", "台积电": "TSMC",
    "台積電": "TSMC", "鸿海": "Foxconn", "鴻海": "Foxconn", "富士康": "Foxconn", "宏碁": "Acer", "华硕": "Asus", "華碩": "Asus",
    "三星": "Samsung", "索尼": "Sony", "日产": "Nissan", "日產": "Nissan", "本田": "Honda", "丰田": "Toyota", "豐田": "Toyota",
    "大众": "Volkswagen", "福斯": "Volkswagen", "宝马": "BMW", "奔驰": "Mercedes-Benz", "通用汽车": "General Motors",
    "福特": "Ford", "波音": "Boeing", "思科": "Cisco", "戴尔": "Dell", "惠普": "HP", "脸书": "Meta", "推特": "X",
    "삼성": "Samsung", "삼성전자": "Samsung", "LG전자": "LG Electronics", "현대차": "Hyundai Motor", "현대자동차": "Hyundai Motor",
    "기아": "Kia", "카카오": "Kakao", "네이버": "Naver", "쿠팡": "Coupang", "롯데": "Lotte", "SK하이닉스": "SK Hynix",
    "마이크로소프트": "Microsoft", "아마존": "Amazon", "구글": "Google", "메타": "Meta", "인텔": "Intel", "테슬라": "Tesla",
    "माइक्रोसॉफ्ट": "Microsoft", "अमेज़न": "Amazon", "अमेजन": "Amazon", "गूगल": "Google", "इंफोसिस": "Infosys",
    "टीसीएस": "TCS", "विप्रो": "Wipro", "मेटा": "Meta", "इंटेल": "Intel", "ओला": "Ola", "पेटीएम": "Paytm",
    "高通": "Qualcomm", "甲骨文公司": "Oracle", "ディズニー": "Disney", "フォルクスワーゲン": "Volkswagen", "ナイキ": "Nike",
    "クアルコム": "Qualcomm", "ネットフリックス": "Netflix", "폭스바겐": "Volkswagen", "오라클": "Oracle", "넷플릭스": "Netflix",
    "디즈니": "Disney", "나이키": "Nike", "퀄컴": "Qualcomm", "Майкрософт": "Microsoft", "Яндекс": "Yandex", "Сбер": "Sber", "Сбербанк": "Sber", "Газпром": "Gazprom",
}

COUNTRY_WORDS = set("""deutschland frankreich österreich schweiz italien spanien europa usa china japan indien amerika
france allemagne espagne italie europe états-unis chine inde japon belgique suisse canada québec
españa francia alemania italia méxico mexico argentina chile colombia perú brasil europa china india
brasil portugal italia frança alemanha espanha eua europa itália milano roma torino
nederland belgië duitsland frankrijk europa polska niemcy europa sverige norge danmark suomi finland
türkiye rusya россия украина украины україна indonesia jakarta vietnam việt nam
""".split())

_CITY = set()


def _cities():
    """Lower-cased names of cities with 15k+ people (GeoNames, already downloaded for the map), to reject
    'Marburg' or 'Wolfsburg' extracted as a company."""
    if _CITY:
        return _CITY
    import io
    import zipfile
    try:
        with zipfile.ZipFile(DATA / "geonames" / "cities5000.zip") as z:
            for line in io.TextIOWrapper(z.open("cities5000.txt"), encoding="utf-8"):
                f = line.split("\t", 15)
                if int(f[14] or 0) >= 15000:
                    _CITY.add(f[1].lower())
                    _CITY.add(f[2].lower())
    except (OSError, KeyError, zipfile.BadZipFile, ValueError, IndexError):
        pass
    _CITY.add("")
    return _CITY


# ------------------------------------------------------------------ numbers
SEP_NUM = r"\d{1,3}(?:[.,    ’']\d{3})+|\d+(?:[.,]\d+)?"


def _to_int(num, mult_word=None, mults=None):
    s = num.strip()
    if re.fullmatch(r"\d{1,3}(?:[.,    ’']\d{3})+", s):
        v = float(re.sub(r"\D", "", s))
    else:
        try:
            v = float(s.replace(",", "."))
        except ValueError:
            return None
    if mult_word:
        mw = mult_word.lower().rstrip(".")
        for k, m in (mults or {}).items():
            if mw.startswith(k):
                v *= m
                break
    v = int(round(v))
    if v < 3 or v > 500_000:
        return None
    return v


def numbers_latin(t, L):
    if not L["job"]:
        return None, None
    mults = L["mult"]
    mw = "|".join(re.escape(k) for k in sorted(mults, key=len, reverse=True))
    mw_rx = rf"(?:\s*(?P<m>{mw})\.?)?" if mw else ""
    rx = re.compile(rf"(?<![\d.,])(?P<n>{SEP_NUM}){mw_rx}\s+(?:\S+\s+){{0,2}}?(?:{L['job']})\b", re.I)
    hc = None
    for m in rx.finditer(t):
        if re.search(r"(?:R\$|US\$|\$|€|£|Rp\.?)\s*$", t[max(0, m.start() - 5):m.start()]):
            continue  # money, not people
        tail = t[m.end():m.end() + 20].lower()
        if re.match(r"\s*(?:euro|eur|€|dollar|\$|franken|kronen|złotych|reais|pesos|rupi|rubl|yen|won|lira)", tail):
            continue
        v = _to_int(m.group("n"), m.groupdict().get("m"), mults)
        if v and not (1990 <= v <= 2035 and not m.groupdict().get("m") and re.fullmatch(r"\d+", m.group("n"))):
            hc = max(hc or 0, v)
    pct = None
    if L["pctw"]:
        m = re.search(rf"(?:(\d+(?:[.,]\d+)?)\s*(?:%|prozent|pour cent|por ciento|por cento|per cento|procent|prosent|procento|"
                      rf"százalék|процент\w*|відсот\w*)|(?:yüzde|%)\s*(\d+(?:[.,]\d+)?))\s+(?:\S+\s+){{0,4}}?(?:{L['pctw']})", t, re.I)
        if m:
            p = float((m.group(1) or m.group(2)).replace(",", "."))
            if 0 < p <= 100:
                pct = p
    return hc, pct


def numbers_cjk(t, code):
    hc = pct = None
    t = unicodedata.normalize("NFKC", t)
    if code == "ja":
        for m in re.finditer(r"(?:約|およそ|最大|計)?(\d[\d,]*(?:\.\d+)?)\s*(万|千)?\s*(?:人|名)(?!程度の対象)", t):
            after, before = t[m.end():m.end() + 4], t[max(0, m.start() - 4):m.start()]
            if "対象" in after or "対象" in before or "規模か" in after:
                continue  # an eligibility pool ("6万人対象") is not a cut
            v = float(m.group(1).replace(",", "")) * {"万": 10_000, "千": 1000}.get(m.group(2), 1)
            if 3 <= v <= 500_000:
                hc = max(hc or 0, int(v))
        m = re.search(r"(?:従業員|社員|人員|全従業員)の?\s*(?:約)?(\d+(?:\.\d+)?)\s*[%％]", t) or \
            re.search(r"(\d+(?:\.\d+)?)\s*[%％]\s*(?:の)?(?:人員|従業員|社員)", t)
        if m:
            pct = float(m.group(1))
    elif code == "zh":
        for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s*(万|千)?\s*(?:余|多)?\s*(?:名|人|位)(?:员工|員工)?", t):
            v = float(m.group(1).replace(",", "")) * {"万": 10_000, "千": 1000}.get(m.group(2), 1)
            if 3 <= v <= 500_000:
                hc = max(hc or 0, int(v))
        m = re.search(r"(?:裁员|裁員|员工|員工|人员|人員)(?:约|約|近|超)?\s*(\d+(?:\.\d+)?)\s*%|(\d+(?:\.\d+)?)\s*%\s*(?:的)?(?:员工|員工|人员|人員)", t)
        if m:
            pct = float(m.group(1) or m.group(2))
    elif code == "ko":
        for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s*(만|천)?\s*명", t):
            if "대상" in t[m.end():m.end() + 4]:
                continue  # eligibility pool
            v = float(m.group(1).replace(",", "")) * {"만": 10_000, "천": 1000}.get(m.group(2), 1)
            if 3 <= v <= 500_000:
                hc = max(hc or 0, int(v))
        m = re.search(r"(?:직원|인력|인원)\s*(?:의\s*)?(\d+(?:\.\d+)?)\s*%", t)
        if m:
            pct = float(m.group(1))
    if pct is not None and not 0 < pct <= 100:
        pct = None
    return hc, pct


# ------------------------------------------------------------------ company
LEGAL = re.compile(r"(?i)(?:[\s,]+(?:ag|se|gmbh|kgaa|co\.?\s*kg|sa|s\.a\.|spa|s\.p\.a\.|srl|nv|n\.v\.|bv|b\.v\.|ab|asa|a/s|oyj|plc|"
                   r"ltd\.?|inc\.?|tbk|persero|sas|s\.a\.s\.|sl|s\.l\.|ltda|s/a|holding|group|gruppe|groupe|grupo|gruppo))+$")
TOKEN_OK = re.compile(r"^[\"'«„“(]*([0-9]*[^\W\d_][\w'’.&+\-/]*|[A-Z0-9][\w&+\-]*)[\"'»”)]*[,;:!?.]?$")
DE_DESC_SUFFIX = re.compile(r"(?i)^[\w-]*(?:konzern|hersteller|bauer|zulieferer|händler|anbieter|dienstleister|versicherer|riese|gigant|"
                            r"betreiber|produzent|entwickler|spezialist|kette|firma|unternehmen|verlag|vermarkter|sender|"
                            r"versorger|bank|gruppe|holding|tochter|start-?up|plattform|marke|werk|standort)$")
CONNECT = {"&", "+", "de", "du", "des", "di", "da", "do", "von", "van", "der", "den", "y", "e", "et", "und", "and", "of", "la", "le"}


def _is_cap(tok):
    t = tok.lstrip("\"'«„“(")
    return bool(t) and (t[0].isupper() or (t[0].isdigit() and re.search(r"[^\W\d_]", t) is not None))


def _clean_name(toks, L, code):
    toks = [t.strip("\"'«»„“”()[],.:;!?") for t in toks]
    toks = [t for t in toks if t]
    while toks and (toks[0].lower() in L["articles"] or toks[0].lower() in L["desc"] or toks[0].lower() in CONNECT):
        toks.pop(0)
    while toks and toks[-1].lower() in CONNECT:
        toks.pop()
    if code == "de":  # "EVOTEC-Aktie", "Siemens-Chef", "VW-Werk", "Werbevermarkter BCN"
        toks = [re.sub(r"(?i)-(?:aktie|chef|chefin|konzern|werk|werke|tochter|mitarbeiter|beschäftigte|standort|gruppe|betriebsrat)$", "", t) for t in toks]
        while len(toks) > 1 and (toks[0].lower() in L["desc"] or DE_DESC_SUFFIX.match(toks[0])) and toks[0].lower() not in ("deutsche", "deutsche bank"):
            toks.pop(0)
    if code in ("tr", "fi", "hu"):
        toks = [re.sub(r"['’]\w+$", "", t) for t in toks]  # Turkish/Finnish case endings: "Ford'da" -> "Ford"
    name = " ".join(toks)
    name = LEGAL.sub("", name).strip(" ,.-")
    if code == "id":
        name = re.sub(r"^(?:PT\.?|PT)\s+", "", name)
    return name


def _valid(name, L, code):
    if not name or len(name) < 2 or len(name.split()) > 4:
        return False
    low = name.lower()
    if low in L["stop"] or low in COUNTRY_WORDS or low in _cities() or name.split()[0].lower() in FUNCTION_WORDS:
        return False
    if low in STOP_ALL:
        return False
    if any(w.strip(".,:;\"'") in REJECT_TOKENS for w in low.split()):
        return False
    vocab = VOCAB.get(code)
    if vocab and code != "de" and all(vocab.get(w.lower().strip("\"'«»„“”"), 0) >= 3 for w in name.split()):
        return False  # every word also shows up lower-case in this language's headlines: a common word, not a name
    if L["job"] and re.fullmatch(rf"(?:{L['job']})", low):
        return False
    if all(w.lower() in L["stop"] or w.lower() in L["desc"] or w.lower() in L["articles"] for w in name.split()):
        return False
    if re.fullmatch(r"[\d\s.,%]+", name) or re.search(r"\b20\d\d\b", name):
        return False
    if L["kw"] and L["kw"].search(name):
        return False
    if code == "de" and len(name.split()) == 1 and re.search(r"(?:ung|heit|keit|schaft|ion|tät|ismus|ierung|abbau|plan|programm|"
                                                            r"krise|welle|ende|aus|zahl|zahlen|markt|branche|industrie|"
                                                            r"politik|gesetz|tarif|streik|lohn)$", low):
        return False  # German common nouns are capitalised too
    if len(name.split()) == 1 and name.isalpha() and name.islower():
        return False
    return True


def _cap_runs(tokens):
    """(start, end) index pairs of capitalised token runs (connectors allowed inside)."""
    runs, i = [], 0
    while i < len(tokens):
        if _is_cap(tokens[i]) and TOKEN_OK.match(tokens[i]):
            j = i + 1
            while j < len(tokens) and (
                    (_is_cap(tokens[j]) and TOKEN_OK.match(tokens[j])) or
                    (tokens[j].lower() in ("&", "+", "de", "di", "von", "van", "du") and j + 1 < len(tokens) and _is_cap(tokens[j + 1]))):
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1
    return runs


def company_latin(seg, L, code, prefix_ok=False):
    tokens = seg.split()
    low = [t.lower().strip("\"'«»„“”(),.:;!?") for t in tokens]
    # 1) "<layoff noun> at <Company>"
    if L["at"]:
        m = re.search(L["at"] + r"\s+(.*)$", seg, re.I)
        if m:
            rest = m.group(1).split()
            k = 0
            while k < len(rest) and (rest[k].lower().strip("\"'«„“") in L["articles"] or rest[k].lower() in L["desc"]
                                     or not _is_cap(rest[k])) and k < 3:
                k += 1
            run = []
            for t in rest[k:]:
                if _is_cap(t) and TOKEN_OK.match(t) and len(run) < 4:
                    run.append(t)
                    if re.search(r"[:,;!?]$", t):
                        break
                else:
                    break
            name = _clean_name(run, L, code)
            if _valid(name, L, code):
                return name, "at"
    # 2) quoted name «Яндекс», „Bosch“
    m = re.search(r"[«„“\"]([^»“”\"]{2,40})[»“”\"]", seg)
    if m and len(m.group(1).split()) <= 4:
        name = _clean_name(m.group(1).split(), L, code)
        if _valid(name, L, code) and _is_cap(name):
            return name, "quoted"
    # 3) subject: the first capitalised run within the first few tokens, followed by a lower-case word or a number
    for a, b in _cap_runs(tokens):
        if a > 4:
            break
        cut = False
        for i in range(a, b):  # "PT Gudang Garam PHK 500 karyawan": the run stops at the keyword
            if L["kw"].search(tokens[i]):
                b, cut = i, True
                break
        if b <= a:
            continue
        if all(low[i] in L["articles"] or low[i] in L["stop"] for i in range(a, b)):
            continue
        nxt = tokens[b] if b < len(tokens) else ""
        if a == 0 and b == len(tokens) and (prefix_ok is False or b > 3):
            break
        if cut or (not nxt and prefix_ok) or nxt and (nxt[0].islower() or nxt[0].isdigit() or nxt in ("-", "–", ":")) or tokens[b - 1].endswith((":", ",")):
            name = _clean_name(tokens[a:b], L, code)
            if _valid(name, L, code):
                return name, "subject"
    return None, None


JA_PREFIX = re.compile(r"^(?:[\[【<＜(（][^\]】>＞)）]{1,12}[\]】>＞)）]\s*)+")
JA_COUNTRY = re.compile(r"^(?:米|英|独|仏|中|韓|台|印|欧|日|豪|加|蘭|瑞|伊|露|米国|中国|韓国|ドイツ|英国)(?=[゠-ヿA-Za-z])")
CJK_STOP = set("""企業 会社 上場企業 大手 日本 政府 業界 黒字 外資 製造業 IT企業 銀行 メガバンク 各社 国内 世界 米国 中国 韓国 米企業
公司 企业 企業 大厂 大廠 科技公司 外企 硅谷 银行 银行业 互联网 车企 車企 多家 巨头 巨頭 美国 美國 中国 中國 日本 韩国 全球 行业 行業 员工 員工 网传 網傳 又一
영국 적자 비전 対象 위기의 독일 인천 매출 중동 재정 내년 시간 네이버 大学 大學 科技 オランダ政府 政府 경기 AI 정부 기업 업계 대기업 은행권 국내 은행 금융권 유통업계 산업계 재계 직원 노조 회사 미국 중국 일본 한국 글로벌""".split())


def company_cjk(seg, code):
    t = unicodedata.normalize("NFKC", seg).strip()
    t = JA_PREFIX.sub("", t)
    if code == "ja":
        m = re.match(r"^(.{2,20}?)(?:、|,|が|は|\s|　)", t)
        cand = m.group(1) if m else None
        if cand:
            cand = JA_COUNTRY.sub("", cand)
            cand = re.sub(r"(?:の|も|で)$", "", cand)
    elif code == "zh":
        m = re.search(r"^(.{2,14}?)(?:宣布|将|將|拟|擬|再度|再次|又|正式|启动|啟動|开启|開啟|开始|開始|计划|計劃|被曝|曝|传|傳|大规模|大規模|全球|在|于|於|今年|也|已|传出|传將|或)?"
                      r"(?:裁员|裁員|人员优化|減員|减员|关闭|關閉|解雇|遣散)", t)
        cand = m.group(1) if m else None
        if not cand:
            m = re.match(r"^(.{2,12}?)(?:[：:，,\s])", t)
            cand = m.group(1) if m else None
        if cand:
            cand = re.sub(r"^(?:美国|美國|美|日本|韩国|韓國|德国|德國|英国|英國|中国|中國|知名|老牌|头部|頭部|科技巨头|科技巨頭|芯片巨头|晶片巨頭)", "", cand)
            cand = re.sub(r"(?:公司|集团|集團)?(?:也|又|再|将|將|拟|擬|宣布|正式|已|或)$", "", cand)
    else:
        m = re.match(r"^(.{2,15}?)(?:,|，|·|…|이|가|은|는|도|\s)", t)
        cand = m.group(1) if m else None
        if cand:
            cand = re.sub(r"^(?:美|日|中|韓|獨|英)(?=[가-힣A-Za-z])", "", cand)
    if not cand:
        return None, None
    cand = cand.strip(" 「」『』《》〈〉\"'“”‘’・")
    if code == "zh" and " " in cand:
        cand = cand.split()[-1]
    if not cand or cand in CJK_STOP or len(cand) < 2 or re.search(r"\d", cand):
        return None, None
    if R[code]["kw"].search(cand) or re.search(r"[、。！？!?]", cand):
        return None, None
    return SCRIPT_NAMES.get(cand, cand), "cjk"


# ------------------------------------------------------------------ gazetteer
class Gazetteer:
    """Known employer names (display -> slug) found anywhere in a headline by word n-gram lookup (fast at any size)."""

    def __init__(self, names):
        self.by_name = {}
        for n, slug in names.items():
            n = n.strip()
            if len(n) >= 3 or (len(n) == 2 and n.isupper()):
                self.by_name.setdefault(n.lower(), (n, slug))
        self.script = sorted(SCRIPT_NAMES, key=len, reverse=True)

    def find(self, t):
        hits = []
        for k in self.script:
            if k in t:
                hits.append(SCRIPT_NAMES[k])
                break
        toks = re.findall(r"[^\W_][\w&+.'’-]*", t)
        toks = [x.rstrip(".'’-") for x in toks]
        best = []
        for i in range(len(toks)):
            if not toks[i][:1].isupper() and not toks[i][:1].isdigit():
                continue
            for n in (4, 3, 2, 1):
                if i + n > len(toks):
                    continue
                k = " ".join(toks[i:i + n]).lower()
                if k in self.by_name:
                    best.append((n, i, self.by_name[k][0]))
                    break
        best.sort(key=lambda x: (-x[0], x[1]))
        return hits + [b[2] for b in best]


# ------------------------------------------------------------------ entry point
def extract(title, code, gaz=None, year=None):
    L = R.get(code)
    if not L or not title:
        return None
    t = unicodedata.normalize("NFKC", title).replace(" ", " ")
    t = re.sub(r"\s+", " ", t).strip()
    if not L["kw"].search(t):
        return None
    if (L["neg"] and L["neg"].search(t)) or (L["roundup"] and L["roundup"].search(t)):
        return None
    segs = [s.strip() for s in re.split(r"\s*[:|｜]\s*|\s+[-–—]\s+", t) if s.strip()]
    prefix = segs[0] if len(segs) > 1 and len(segs[0].split()) <= 3 else None  # "Tamedia: 400 Personen ..."
    segs.sort(key=lambda s: 0 if L["kw"].search(s) else 1)
    co = method = None
    for s in segs:
        if code in CJK:
            co, method = company_cjk(s, code)
        elif code in LATIN:
            co, method = company_latin(s, L, code, prefix_ok=(s == prefix))
        if co:
            break
    if gaz is not None:
        hits = gaz.find(t)
        if hits and (not co or method in ("subject", "cjk", "quoted") and co not in hits):
            # a known employer named in the headline beats a guessed subject
            if not co or co.lower() not in {h.lower() for h in hits}:
                co, method = hits[0], "gazetteer"
    if not co:
        return None
    co = SCRIPT_NAMES.get(co, co)
    if code in CJK:
        hc, pct = numbers_cjk(t, code)
    else:
        hc, pct = numbers_latin(t, L)
        # "fired", "ontslagen", "sa thải", "звільнив" also describe one coach or minister. Without a number, a plural
        # job noun or a collective layoff noun ("Stellenabbau bei"), it is not a layoff report.
        known = method == "gazetteer" or (gaz is not None and co.lower() in gaz.by_name)
        if not (hc or pct or method == "at" or known or (L["job"] and re.search(rf"\b(?:{L['job']})", t, re.I))):
            return None
    horizon = None
    if L["plan"]:
        m = L["plan"].search(t)
        if m:
            yrs = [g for g in m.groups() if g]
            y = int(yrs[0]) if yrs and len(yrs[0]) == 4 else (2000 + int(yrs[0]) if yrs and len(yrs[0]) == 2 else None)
            if y is None or (year and y > year):
                horizon = str(y) if y else "multi-year"
    years = [int(y) for y in re.findall(r"(?<!\d)(20\d\d)(?!\d)", t)]
    if not horizon and ((L["past"] and L["past"].search(t)) or (year and any(y < year for y in years))):
        hc = pct = None  # a past total, not this event
    if PROTEST.search(t):
        hc = None  # "400 Personen gegen Stellenabbau" counts protesters
    spec = bool(L["spec"] and L["spec"].search(t))
    kind = "plan" if horizon and (hc or pct) else "layoff"
    if code not in ("ja",) and L["buyout"] and L["buyout"].search(t):
        kind = "buyout"
    return {"company": co, "headcount": hc, "pct": pct, "kind": kind, "speculative": spec, "country": None,
            "industry": None, "method": f"{code}-{method}", "horizon": horizon}
