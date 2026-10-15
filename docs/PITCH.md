# EchoBreast — Pitch de 5 minutes

> Phrase-clé à répéter au début ET à la fin :
> **« EchoBreast aide les professionnels à décider quoi relire en premier ; il ne décide jamais à leur place. »**

Rôles conseillés : **A** = orateur·rice principal·e, **B** = pilote de la démo (clavier). B a la démo ouverte
*avant* de monter sur scène (onglet « Analyse » chargé, cas 1 sélectionné) et la vidéo de secours prête.

---

## 0:00 – 0:40 · Le problème (A) — 40 s

> « Octobre Rose. Chaque année, le cancer du sein est l'un des cancers les plus fréquents chez les femmes
> dans le monde — [CHIFFRE OMS VÉRIFIÉ + année]. Au Burkina Faso, [CHIFFRE LOCAL VÉRIFIÉ + source].
>
> Détecté tôt, il se soigne beaucoup mieux. Mais dans beaucoup de services, il y a **peu de radiologues
> pour beaucoup d'examens**, du matériel modeste et une connexion fragile.
>
> Question : **comment aider ces équipes à repérer plus vite les examens les plus urgents ?** »

🖼 Diapo 1 : un seul chiffre en très gros + ruban rose.
⚠️ Ne dire **que** des chiffres vérifiés, avec source et année affichées sur la diapo.

## 0:40 – 1:10 · Où intervient EchoBreast (A) — 30 s

> « Le parcours, c'est : examen clinique → **échographie** → prélèvement → laboratoire → traitement.
> EchoBreast intervient ici, à l'échographie : il **trie la pile** d'examens du plus au moins urgent à relire.
> Il ne pose aucun diagnostic. »

🖼 Diapo 2 : le parcours en 5 pictos, l'étape « échographie » surlignée en rose.

## 1:10 – 3:40 · Démonstration en direct (B pilote, A commente) — 2 min 30

1. **Cas rouge (≈ 40 s)** — Analyse → cas malin.
   > « En quelques secondes : trois probabilités, un niveau **rouge** avec icône et libellé — jamais la couleur
   > seule — et le **contour** de la zone suspecte, dans la couleur du niveau. »
   Activer **Grad-CAM** : « Ce que le modèle a regardé. Ce n'est pas la position exacte de la lésion — on le dit. »

2. **Cas orange (≈ 25 s)** —
   > « Ici le modèle hésite. Règle de prudence : **en cas de doute, orange**. On préfère une relecture de trop
   > qu'un cancer manqué. »

3. **Liste de priorité (≈ 45 s)** — onglet Liste → « Utiliser tous les cas de démo ».
   > « Lundi matin, 30 échographies. EchoBreast les classe : rouges en haut, puis orange, puis vert.
   > C'est l'idée du tri par score de risque évaluée dans l'essai suédois MASAI en mammographie —
   > nous, en version légère, sur un simple ordinateur, sans GPU. »

4. **Fiche PDF (≈ 15 s)** — retour Analyse → Télécharger la fiche.
   > « Image annotée, probabilités, version du modèle, avertissement. Zéro donnée d'identité. »

5. **Le cas où le modèle se trompe (≈ 25 s)** — ouvrir le cas d'erreur, « Révéler la vérité terrain ».
   > « Et voici un cas où **le modèle se trompe**. On vous le montre exprès : c'est exactement pour ça
   > que la décision reste au professionnel. »

## 3:40 – 4:20 · Résultats, éthique, limites (A) — 40 s

Onglet **Limites et sources** à l'écran.

> « Entraîné sur BUSI, 780 échographies publiques, version nettoyée des doublons.
> Sur des images de test jamais vues : sensibilité de **[X %]** pour les cas malins (orange ou rouge),
> AUC de **[Y]**, **[N]** cas malins classés vert. Ces chiffres sont affichés dans l'outil, sans arrondi
> en notre faveur.
>
> Limite n°1, et on la dit en premier : **les images viennent d'Égypte. Rien ne prouve que le modèle
> fonctionne sur des patientes burkinabè.** Ce n'est pas un dispositif médical, aucune image n'est conservée. »

## 4:20 – 5:00 · Perspectives et conclusion (A) — 40 s

> « Prochaines étapes : un partenariat avec un service de radiologie pour **collecter des données locales
> dans un cadre éthique**, évaluer avec des radiologues, puis une version **hors ligne**.
> La même méthode peut servir pour la mammographie, le col de l'utérus ou le paludisme.
>
> EchoBreast aide les professionnels à décider quoi relire en premier ; **il ne décide jamais à leur place.**
> Merci. »

🖼 Diapo finale : logo, phrase-clé, QR code vers la démo en ligne, noms de l'équipe.

---

## Questions probables du jury (réponses en 15 s)

| Question | Réponse |
|---|---|
| Vos chiffres sont-ils fiables ? | Mesurés une seule fois sur un test séparé, après dédoublonnage. Probablement optimistes car pas d'identifiant patiente — on l'écrit dans l'outil. |
| Pourquoi pas un diagnostic ? | Ce n'est ni validé cliniquement ni un dispositif médical. Notre valeur : gagner du temps sur l'ordre de relecture. |
| Et les faux négatifs ? | Seuil orange fixé pour viser ≥ 95 % de sensibilité sur la validation, orange par défaut en cas de doute, avertissement permanent. |
| Biais ? | Une seule source, aucune donnée d'Afrique de l'Ouest ; la littérature rapporte plus de faux positifs chez les femmes noires. D'où la priorité : données locales. |
| Ça tourne où ? | Sur CPU, < 3 s par image, en ligne ou en local sur un portable. |
| Modèle économique ? | Outil libre pour services publics ; financement par partenariats santé / ONG pour la phase de validation. |

## Checklist jour J

- [ ] Démo **locale** lancée sur le portable (pas seulement en ligne).
- [ ] Vidéo de secours de la démo (90 s) sur le bureau.
- [ ] Chiffres de la diapo 1 vérifiés et sourcés ; chiffres de résultats = ceux de `models/metrics.json`.
- [ ] 3 répétitions chronométrées. Si > 5:00 : couper d'abord le cas orange, puis Grad-CAM.
- [ ] Zoom du navigateur à 125 % pour la lisibilité sur projecteur.
