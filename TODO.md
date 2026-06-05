DONE:
- cambiare testi (multilingua) per richiesta inviata a operatore umano, fallimento ticket inviato (anche due volte doppi punti), messaggio test demo locale no AI, placeholder invio email utente

- cambiare emoji pollici e migliorare coerenza con stile all'hover e alla pressione, soprattuto rendendo ugualmente visibili i tasti feedback sia in versione tema chiato che tema scuro. poi migliora allinamento verticale rispetto ai pulsanti feedback del testo feedback

- non devono essere selezionabili domande preimpostate e feedback messaggi quando si è in attesa che venga inserita email utente per supporto (come infatti sono disabilitati mentre il bot ragiona/scrive)

- email inviata come messaggio utente normale che compare in chat e bot fa animazione di ragionamento/scrittura prima di scrivere l'esito di successo dell'avvenuta richiesta o fallimento ticket FATTO

- Tutte le richieste devono essere tradotte in italiano prima della ricerca nella kb, mentre tutte le risposte del bot devono essere tradotte nella lingua corrente selezionata nella UI. poi non voglio switch automatico della lingua rilevata del messaggio in modo harcodato con dizionario di parole frequenti. voglio un rilevamento robusto basato su llm che identifichi la lingua tra quelle disponbili nel chatbot e aggiorn di consegunza la UI e serva per la traduzione del messaggio per la dashboard operatore FATTO

- non voglio salvare original_message e translated_message perché operatore puo visualizzare tutta la chat e tradurla premendo su traduci conversazione in un solo colpo quando verrà sviluppata la dashboard operatore. poi a che serve nella tabella ticket il feedback_messages_id? si può rimuovere o è vitale per la dashboard operatore?

- nel summary AI non deve comparire "Ecco un riassunto della chat in italiano in 2 frasi:...", ma deve iniziare direttamente con il riassunto, senza introduzione della risposta LLM", quindi penso si debba migliroare il prompt. Voglio che sia in riferimento principalmente all'ultimo messaggio che ha creato l'escalation e un po sulla cronologia della chat perchè abbiamo rimosso original_meassage e translated_message che fanno riferimento al messaggio che ha generato l'escalation.

- se l'utente preme la X per annullare il processo di ticketing deve essere cancellato il messaggio di help di attesa email utente del bot e il pulsante feedback che ha generato la potenziale richiesta di help deve essere riportato a nessuno stato (nessuno dei due pulsanti feedback premuti). poi ancora non è centrato perfettamentre emoji su tutti i dispositivi, perché lo span non ha spazi interni sopra e sotto uguali per conformazione propria dell'emoji dei pollici.

- non mi piace l'effetto quando togli il messaggio di helper premendo sulla X, che si sollevano anche i floating buttons su mobile. non devi muovere la posizione dei floating in alto, ma bensì devo scorrere la chat verso il basso, fino al limite impostato a ridosso dei floating button, che restano fermi.

- poi nel db, voglio che created_at segua il vero orario che ho io sul pc e comunque noi qui in italia. di conseguenza, voglio anche data e ora sotto i messaggi sia user che bot con lo stesso stile del testo "ti è stato utile?" del feedback.

- chat_user e chat_user_dark ora sono la stessa immagine come contenuto, utilizza solo chat_user come default per entrambe le modalità e elimina chat_user_dark come riferimento e come asset.

- immagini e audio non devono aggiungere trascrizioni e estrazioni di testo al messaggio in chiaro, le info estratte devono essere usate solo under the hood, non mostrare trascrizioni/estrazioni di nulla nei messaggi.


TO DO:
- voglio che anche messaggi precedenti possano aprire escalation anche se non sono ultimo messaggio inviato. semplicemente invece di avere feedbakc_message_id nella tabella tickets viene salvato escalated_message_id ovvero id della tabella messages relativo al messaggio su cui è stato richiesto il feedback. unico vincolo mentre è aperta una richiesta di escalation non posso premere altri feedback negativi e duplicarle escalation, uno per volta ma anche in maniera retroattiva.

- text to speech lato frontend su tutti i dispositivi quando l'utente invia un messaggio vocale la risposta, oltre a essere visualizzata in maniera testuale come ogni messaggio deve essere anche letta in automatico nella stessa lingua impostata nella UI, solo una volta quando la risposta viene ricevuta dal bot e compare nella chat.

- quando passo da arabo a un altra lingua poi non viene mantenuto il distacco dai pulsanti floating all'ultimo messaggio come invece avviene passando da una lingua all'altra (non arabo). solo su mobile. quindi voglio che mi riporti a ogni switch di lingua quanto piu giu possibile nella message area, nello stesso modo che succede quando appare un nuovo messaggio nella chat.

- verifiche ridondanze in tutta la codebase o elementi non utilizzati o non rilevanti, mantenendo il funzionamento e lo stile.

- rivedere grafiche, favorendo introduzioni loghi e mascotte

- dashboard operatore

- verificare correttezza e completezza dati generati/salvati nel database (se sono coerenti con quello che succede)

- capire rotta kpis