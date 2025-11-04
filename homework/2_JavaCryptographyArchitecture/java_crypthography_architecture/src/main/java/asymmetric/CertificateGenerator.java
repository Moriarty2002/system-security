package asymmetric;

import org.bouncycastle.asn1.x500.X500Name;
import org.bouncycastle.asn1.x509.BasicConstraints;
import org.bouncycastle.asn1.x509.Extension;
import org.bouncycastle.asn1.x509.KeyUsage;
import org.bouncycastle.asn1.x509.SubjectPublicKeyInfo;
import org.bouncycastle.asn1.x509.GeneralName;
import org.bouncycastle.asn1.x509.GeneralNames;
import org.bouncycastle.asn1.x509.Extensions;
import org.bouncycastle.asn1.x509.ExtensionsGenerator;
import org.bouncycastle.asn1.pkcs.Attribute;
import org.bouncycastle.asn1.ASN1Set;
import org.bouncycastle.asn1.pkcs.PKCSObjectIdentifiers;
import org.bouncycastle.cert.X509CertificateHolder;
import org.bouncycastle.cert.X509v3CertificateBuilder;
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter;
import org.bouncycastle.cert.jcajce.JcaX509ExtensionUtils;
import org.bouncycastle.operator.ContentSigner;
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder;
import org.bouncycastle.pkcs.PKCS10CertificationRequest;
import org.bouncycastle.pkcs.PKCS10CertificationRequestBuilder;
import org.bouncycastle.pkcs.jcajce.JcaPKCS10CertificationRequestBuilder;

import javax.security.auth.x500.X500Principal;
import java.math.BigInteger;
import java.security.KeyPair;
import java.security.PrivateKey;
import java.security.SecureRandom;
import java.security.cert.X509Certificate;
import java.util.Date;

public class CertificateGenerator {

    public static String[] usageNames = {
            "Digital Signature",    // (0)
            "Non-Repudiation",      // (1)
            "Key Encipherment",     // (2)
            "Data Encipherment",    // (3)
            "Key Agreement",        // (4)
            "KeyCert Sign",         // (5)
            "CRL Sign",             // (6)
            "Encipher Only",        // (7)
            "Decipher Only"         // (8)
    };

    public static X509Certificate generateCertificateSelfSigned(String subjectIssuerName, KeyPair keyPair,
                                                                Date notBefore, Date notAfter, String sigAlg)
    throws Exception {
        X500Name subjectIssuer = new X500Name(subjectIssuerName);

        // generate random serial number
        BigInteger serialNumber = new BigInteger(64, new SecureRandom());

        // get CA public key info
        SubjectPublicKeyInfo publicKeyInfo = SubjectPublicKeyInfo.getInstance(
                keyPair.getPublic().getEncoded()
        );

        X509v3CertificateBuilder certBuilder = new X509v3CertificateBuilder(
                subjectIssuer,
                serialNumber,
                notBefore,
                notAfter,
                subjectIssuer, // self-signed
                publicKeyInfo
        );

        KeyUsage keyUsage = new KeyUsage(KeyUsage.keyCertSign | KeyUsage.cRLSign);
        certBuilder.addExtension(Extension.keyUsage, true, keyUsage);
        certBuilder.addExtension(Extension.basicConstraints, true, new BasicConstraints(true));


        // create content signer using CA private key
        ContentSigner signer = new JcaContentSignerBuilder(sigAlg)
                .setProvider("BC")
                .build(keyPair.getPrivate());

        X509CertificateHolder certHolder = certBuilder.build(signer);

        return new JcaX509CertificateConverter()
                .setProvider("BC")
                .getCertificate(certHolder);
    }

    /**
     * Generates a PKCS#10 Certificate Signing Request (CSR)
     *
     * @param subjectDN     The subject's Distinguished Name (e.g. "CN=example.com, O=MyOrg, C=US")
     * @param keyPair       The subject’s key pair
     * @param signatureAlg  Signature algorithm (e.g. "SHA256withRSA")
     * @return A PKCS10CertificationRequest (the CSR)
     * @throws Exception if CSR creation fails
     */
    public static PKCS10CertificationRequest generateCSR(String subjectDN, KeyPair keyPair, String signatureAlg)
            throws Exception {

        // default: no SANs requested
        return generateCSR(subjectDN, keyPair, signatureAlg, null);
    }

    /**
     * Generate a CSR and optionally include Subject Alternative Names as an extension request.
     * The SAN entries may be DNS names or IPv4 addresses (detected heuristically).
     */
    public static PKCS10CertificationRequest generateCSR(String subjectDN, KeyPair keyPair, String signatureAlg, String[] subjectAltNames)
            throws Exception {

        PKCS10CertificationRequestBuilder p10Builder =
                new JcaPKCS10CertificationRequestBuilder(
                        new X500Principal(subjectDN),
                        keyPair.getPublic()
                );

        // if SANs are provided, add them in the extensionRequest attribute of the CSR
        if (subjectAltNames != null && subjectAltNames.length > 0) {
            GeneralName[] gns = new GeneralName[subjectAltNames.length];
            for (int i = 0; i < subjectAltNames.length; i++) {
                String name = subjectAltNames[i];
                if (name.matches("\\d+\\.\\d+\\.\\d+\\.\\d+")) {
                    gns[i] = new GeneralName(GeneralName.iPAddress, name);
                } else {
                    gns[i] = new GeneralName(GeneralName.dNSName, name);
                }
            }

            GeneralNames subjectAltName = new GeneralNames(gns);
            ExtensionsGenerator extGen = new ExtensionsGenerator();
            extGen.addExtension(Extension.subjectAlternativeName, false, subjectAltName);
            Extensions exts = extGen.generate();

            p10Builder.addAttribute(PKCSObjectIdentifiers.pkcs_9_at_extensionRequest, exts);
        }

        JcaContentSignerBuilder csBuilder =
                new JcaContentSignerBuilder(signatureAlg)
                        .setProvider("BC");
        ContentSigner signer = csBuilder.build(keyPair.getPrivate());

        return p10Builder.build(signer);
    }

    /**
     * Signs a CSR with the CA's private key to issue a certificate.
     *
     * @param csr           The CSR to sign
     * @param issuerDN      The CA’s Distinguished Name (DN)
     * @param caPrivateKey  The CA’s private key
     * @param notBefore     Certificate validity start date
     * @param notAfter      Certificate validity end date
     * @param sigAlg        Signature algorithm (e.g. "SHA256withRSA")
     * @return Signed X509Certificate
     * @throws Exception if signing fails
     */
    public static X509Certificate signCSR(
            PKCS10CertificationRequest csr,
            String issuerDN,
            PrivateKey caPrivateKey,
            Date notBefore,
            Date notAfter,
            String sigAlg
    ) throws Exception {

        X500Name issuer = new X500Name(issuerDN);
        X500Name subject = csr.getSubject();

        SubjectPublicKeyInfo subjectPublicKeyInfo = csr.getSubjectPublicKeyInfo();

        BigInteger serialNumber = new BigInteger(64, new SecureRandom());

        X509v3CertificateBuilder certBuilder = new X509v3CertificateBuilder(
                issuer,
                serialNumber,
                notBefore,
                notAfter,
                subject,
                subjectPublicKeyInfo
        );

        JcaX509ExtensionUtils extUtils = new JcaX509ExtensionUtils();
        certBuilder.addExtension(
                org.bouncycastle.asn1.x509.Extension.subjectKeyIdentifier,
                false,
                extUtils.createSubjectKeyIdentifier(subjectPublicKeyInfo)
        );

                // If the CSR contains an extensionRequest with SANs, copy the SAN extension into the issued certificate
                Attribute[] attributes = csr.getAttributes();
                if (attributes != null) {
                        for (Attribute attr : attributes) {
                                if (attr.getAttrType().equals(PKCSObjectIdentifiers.pkcs_9_at_extensionRequest)) {
                                        ASN1Set attrValues = attr.getAttrValues();
                                        if (attrValues != null && attrValues.size() > 0) {
                                                Extensions reqExts = Extensions.getInstance(attrValues.getObjectAt(0));
                                                org.bouncycastle.asn1.x509.Extension sanExt = reqExts.getExtension(Extension.subjectAlternativeName);
                                                if (sanExt != null) {
                                                        certBuilder.addExtension(Extension.subjectAlternativeName, sanExt.isCritical(), sanExt.getParsedValue());
                                                }
                                        }
                                }
                        }
                }

        // sign certificate with CA’s private key
        ContentSigner signer = new JcaContentSignerBuilder(sigAlg)
                .build(caPrivateKey);

        X509CertificateHolder certHolder = certBuilder.build(signer);

        return new JcaX509CertificateConverter()
                .setProvider("BC")
                .getCertificate(certHolder);
    }

}
