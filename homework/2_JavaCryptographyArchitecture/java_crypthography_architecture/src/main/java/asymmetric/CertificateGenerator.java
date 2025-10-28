package asymmetric;

import org.bouncycastle.asn1.x500.X500Name;
import org.bouncycastle.asn1.x509.SubjectPublicKeyInfo;
import org.bouncycastle.cert.X509CertificateHolder;
import org.bouncycastle.cert.X509v3CertificateBuilder;
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter;
import org.bouncycastle.cert.jcajce.JcaX509ExtensionUtils;
import org.bouncycastle.openssl.MiscPEMGenerator;
import org.bouncycastle.openssl.jcajce.JcaPEMWriter;
import org.bouncycastle.openssl.jcajce.JcePEMEncryptorBuilder;
import org.bouncycastle.operator.ContentSigner;
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder;
import org.bouncycastle.pkcs.PKCS10CertificationRequest;
import org.bouncycastle.pkcs.PKCS10CertificationRequestBuilder;
import org.bouncycastle.pkcs.jcajce.JcaPKCS10CertificationRequestBuilder;

import java.io.FileWriter;
import java.math.BigInteger;
import java.security.KeyPair;
import java.security.PrivateKey;
import java.security.SecureRandom;
import java.security.cert.X509Certificate;
import java.util.Date;

public class CertificateGenerator {

    public static X509Certificate generateCertificateSelfSigned(String subjectIssuerName, KeyPair keyPair,
                                                                Date notBefore, Date notAfter, String sigAlg)
    throws Exception {
        X500Name subjectIssuer = new X500Name(subjectIssuerName);

        // Generate random serial number
        BigInteger serialNumber = new BigInteger(64, new SecureRandom());

        // Get public key info
        SubjectPublicKeyInfo publicKeyInfo = SubjectPublicKeyInfo.getInstance(
                keyPair.getPublic().getEncoded()
        );

        // Build the certificate
        X509v3CertificateBuilder certBuilder = new X509v3CertificateBuilder(
                subjectIssuer,
                serialNumber,
                notBefore,
                notAfter,
                subjectIssuer,
                publicKeyInfo
        );

        // Create content signer using the private key
        ContentSigner signer = new JcaContentSignerBuilder(sigAlg)
                .setProvider("BC")
                .build(keyPair.getPrivate());

        // Generate the certificate
        X509CertificateHolder certHolder = certBuilder.build(signer);

        // Convert to X509Certificate
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

        X500Name subject = new X500Name(subjectDN);

        PKCS10CertificationRequestBuilder p10Builder =
                new JcaPKCS10CertificationRequestBuilder(subject, keyPair.getPublic());

        ContentSigner signer = new JcaContentSignerBuilder(signatureAlg)
                .build(keyPair.getPrivate());

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

        // Add basic extensions (optional, but good practice)
        JcaX509ExtensionUtils extUtils = new JcaX509ExtensionUtils();
        certBuilder.addExtension(
                org.bouncycastle.asn1.x509.Extension.subjectKeyIdentifier,
                false,
                extUtils.createSubjectKeyIdentifier(subjectPublicKeyInfo)
        );

        // Sign certificate with CA’s private key
        ContentSigner signer = new JcaContentSignerBuilder(sigAlg)
                .build(caPrivateKey);

        X509CertificateHolder certHolder = certBuilder.build(signer);

        return new JcaX509CertificateConverter()
                .setProvider("BC")
                .getCertificate(certHolder);
    }


    //"CN=www.polimi.it, OU=Dipartimento di Elettronica, Informazione e Bioingegneria, O=Politecnico di Milano, L=Milano, ST=MI, C=IT"
}
